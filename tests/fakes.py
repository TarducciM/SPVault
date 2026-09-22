"""Server SharePoint finto (API v2.0: drives, children, delta, content, shares, root:/percorso) per i test."""
import base64
from datetime import datetime, timezone
from urllib.parse import quote, unquote

import requests

import spvault as spb

SITE = "https://t.sharepoint.com/sites/Test"
DRIVE = f"{SITE}/_api/v2.0/drives/D1"


def reference_quickxorhash(chunks) -> str:
    """Traduzione riga per riga dell'implementazione C# di riferimento di Microsoft."""
    width, shift, m64 = 160, 11, (1 << 64) - 1
    cells = [0, 0, 0]
    shift_so_far = length = 0
    for array in chunks:
        cb = len(array)
        idx, off = shift_so_far // 64, shift_so_far % 64
        for i in range(min(cb, width)):
            is_last = idx == 2
            bits = 32 if is_last else 64
            if off <= bits - 8:
                for j in range(i, cb, width):
                    cells[idx] ^= (array[j] << off) & m64
            else:
                idx2 = 0 if is_last else idx + 1
                low = bits - off
                x = 0
                for j in range(i, cb, width):
                    x ^= array[j]
                cells[idx] ^= (x << off) & m64
                cells[idx2] ^= x >> low
            off += shift
            while off >= bits:
                idx = 0 if is_last else idx + 1
                off -= bits
        shift_so_far = (shift_so_far + shift * (cb % width)) % width
        length += cb
    rgb = bytearray(cells[0].to_bytes(8, "little") + cells[1].to_bytes(8, "little")
                    + (cells[2] & m64).to_bytes(8, "little")[:4])
    for i, b in enumerate(length.to_bytes(8, "little")):
        rgb[12 + i] ^= b
    return base64.b64encode(rgb).decode()


def qxh(data: bytes) -> str:
    h = spb.QuickXorHash()
    h.update(data)
    return h.digest()


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Resp:
    def __init__(self, status=200, body=None, content=b"", break_after=None):
        self.status_code, self.body, self.content = status, body, content
        self.headers = {}
        self.ok = status < 400
        self.text = str(body)
        self.break_after = break_after

    def json(self):
        return self.body

    def iter_content(self, n):
        for i in range(0, len(self.content), 1000):
            if self.break_after is not None and i >= self.break_after:
                raise requests.exceptions.ChunkedEncodingError("connessione persa")
            yield self.content[i:i + 1000]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


class Server:
    """Libreria in memoria. Simula anche i guasti: connessione che cade, sessione
    scaduta, hash sbagliato, file assenti dall'elenco delta, file non accessibili."""

    def __init__(self):
        self.items, self.ver, self.changed, self.deleted = {}, 0, {}, {}
        self.break_once, self.unauth_once, self.bad_hash = set(), False, set()
        self.hidden = set()       # esistono ma l'elenco delta non li riporta
        self.private = set()      # esistono ma l'utente non li vede (permessi)
        self.always_fail = set()  # download sempre in errore
        self.ghosts = {}          # riportati dall'elenco delta ma inesistenti
        self.shares = {}          # link di condivisione (o indirizzo) -> id dell'elemento condiviso
        self.guest = False        # ospite: non vede l'elenco delle librerie né il delta della libreria
        self.downloads, self.ranges, self.logins, self.prefer, self.urls = [], [], [], [], []
        self.t = 1_700_000_000

    # --- modifiche alla libreria
    def _bump(self, i):
        self.ver += 1
        self.changed[i] = self.ver
        self.deleted.pop(i, None)

    def add(self, i, name, parent, kind="file", content=b""):
        self.t += 60
        self.items[i] = dict(name=name, parent=parent, kind=kind, content=content, mtime=self.t, c=1)
        self._bump(i)

    def modify(self, i, content):
        it = self.items[i]
        self.t += 60
        it.update(content=content, mtime=self.t, c=it["c"] + 1)
        self._bump(i)

    def touch_metadata(self, i):  # es. colonna modificata: cambia la data, non il contenuto
        self.t += 60
        self.items[i]["mtime"] = self.t
        self._bump(i)

    def rename(self, i, name=None, parent=None):
        if name:
            self.items[i]["name"] = name
        if parent:
            self.items[i]["parent"] = parent
        self._bump(i)

    def delete(self, i):
        del self.items[i]
        self.ver += 1
        self.deleted[i] = self.ver
        self.changed.pop(i, None)

    def build_default_library(self):
        self.add("ROOT", "root", None, "root")
        self.add("A", "2. Projects", "ROOT", "folder")
        self.add("B", "3. Marketing", "ROOT", "folder")
        self.add("TOP", "Inventory.xlsx", "ROOT", content=b"xlsx-1")
        self.add("A1", "Progetto1", "A", "folder")
        self.add("f1", "logo.psd", "A1", content=bytes(range(256)) * 20)
        self.add("f2", "bg.png", "A1", content=b"png-1" * 100)
        self.add("f3", "note.txt", "A", content=b"note")
        self.add("big", "grande.psd", "A", content=bytes(reversed(range(256))) * 80)
        self.add("E1", "Vuota", "A", "folder")
        self.add("NB", "Appunti", "A", "package")
        self.add("NB1", "sezione.one", "NB", content=b"one")
        self.add("g1", "online.psd", "B", content=b"online")

    # --- rappresentazione API
    def _children(self, i):
        return [c for c, it in self.items.items() if it["parent"] == i]

    def tree_size(self, i):
        if self.items[i]["kind"] == "file":
            return len(self.items[i]["content"])
        return sum(self.tree_size(c) for c in self._children(i))

    def js(self, i):
        it = self.items[i]
        d = {"id": i, "name": it["name"], "parentReference": {"id": it["parent"]},
             "lastModifiedDateTime": iso(it["mtime"])}
        if it["kind"] == "root":
            d.update(root={}, folder={"childCount": len(self._children(i))}, size=self.tree_size(i))
        elif it["kind"] == "folder":
            d.update(folder={"childCount": len(self._children(i))}, size=self.tree_size(i))
        elif it["kind"] == "package":
            d.update(package={"type": "oneNote"}, size=self.tree_size(i))
        else:
            h = "XXXXbadhashXXXXXXXXXXXXXXX=" if i in self.bad_hash else qxh(it["content"])
            d.update(file={"hashes": {"quickXorHash": h}}, size=len(it["content"]),
                     cTag=f"c:{i},{it['c']}")
        return d

    def _delta_ids(self):
        return sorted(i for i in self.items if i not in self.hidden | self.private)

    def web_url(self, i):
        names = []
        while self.items[i]["kind"] != "root":
            names.append(self.items[i]["name"])
            i = self.items[i]["parent"]
        return f"{SITE}/Documenti" + "".join("/" + quote(n) for n in reversed(names))

    def _by_path(self, path):
        """Elemento dal percorso dentro la libreria (segmenti codificati come negli URL)."""
        i = "ROOT"
        for name in filter(None, path.split("/")):
            name = unquote(name)
            match = [c for c in self._children(i) if self.items[c]["name"].casefold() == name.casefold()]
            if not match:
                return None
            i = match[0]
        return i

    def _share(self, url, headers):
        token = url.split("/shares/u!")[1].split("/")[0]
        assert "=" not in token and "+" not in token and "/" not in token  # base64url senza padding
        link = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        self.prefer.append(headers.get("Prefer"))
        i = self.shares.get(link)
        if i not in self.items:
            return Resp(404, {"error": {"message": "The sharing link no longer exists"}})
        d = self.js(i)
        d["parentReference"]["driveId"] = "D1"
        d["webUrl"] = self.web_url(i)
        return Resp(body=d)

    # --- requests.Session.get
    def get(self, url, stream=False, headers=None, timeout=None):
        headers = headers or {}
        self.urls.append(url)
        if self.unauth_once and "/content" in url:
            self.unauth_once = False
            return Resp(401, {"error": {"message": "expired"}})
        if url.startswith(f"{SITE}/_api/v2.0/drives?"):
            if self.guest:
                return Resp(403, {"error": {"message": "accessDenied"}})
            return Resp(body={"value": [{"id": "X", "name": "Altro", "webUrl": f"{SITE}/Altro"},
                                        {"id": "D1", "name": "Documenti", "webUrl": f"{SITE}/Documenti"}]})
        if url.startswith(f"{SITE}/_api/v2.0/shares/u!") and url.split("?")[0].endswith("/driveItem"):
            return self._share(url, headers)
        if url.startswith(f"{DRIVE}/root:/"):
            i = self._by_path(url.split("/root:/")[1].split("?")[0].rstrip(":"))
            return Resp(body=self.js(i)) if i else Resp(404, {"error": {"message": "itemNotFound"}})
        if self.guest and url.startswith(f"{DRIVE}/root/"):
            return Resp(403, {"error": {"message": "accessDenied"}})
        if url.startswith(f"{SITE}/_api/web/currentuser"):
            return Resp(body={"Email": "me@test"})
        if url.startswith(f"{DRIVE}/root/children"):
            return Resp(body={"value": [self.js(i) for i in self._children("ROOT")]})
        if url.startswith(f"{DRIVE}/items/") and "/children?" in url:
            i = url.split("/items/")[1].split("/")[0]
            return Resp(body={"value": [self.js(c) for c in self._children(i) if c not in self.private]})
        if url.startswith(f"{DRIVE}/items/") and "?$select" in url:
            return Resp(body=self.js(url.split("/items/")[1].split("?")[0]))
        if url.startswith(f"{DRIVE}/root/delta?$top"):
            url = f"{DRIVE}/root/delta?token=full-0-{self.ver}"
        if url.startswith(f"{DRIVE}/root/delta?token=full-"):
            off, ver = map(int, url.split("full-")[1].split("-"))
            ids = self._delta_ids() + sorted(self.ghosts)
            body = {"value": [self.ghosts[i] if i in self.ghosts else self.js(i) for i in ids[off:off + 3]]}
            if off + 3 < len(ids):
                body["@odata.nextLink"] = f"{DRIVE}/root/delta?token=full-{off + 3}-{ver}"
            else:
                body["@odata.deltaLink"] = f"{DRIVE}/root/delta?token=v{ver}"
            return Resp(body=body)
        if url.startswith(f"{DRIVE}/root/delta?token=v"):
            since = int(url.split("token=v")[1])
            if since < 0:
                return Resp(410, {"error": {"message": "resyncRequired"}})
            visible = set(self._delta_ids())
            page = [self.js(i) for i, v in self.changed.items() if v > since and i in visible]
            page += [{"id": i, "deleted": {}} for i, v in self.deleted.items() if v > since]
            return Resp(body={"value": page, "@odata.deltaLink": f"{DRIVE}/root/delta?token=v{self.ver}"})
        if url.startswith(f"{DRIVE}/items/") and url.endswith("/content"):
            i = url.split("/items/")[1].split("/")[0]
            if i not in self.items:
                return Resp(404, {"error": {"message": "not found"}})
            if i in self.always_fail:
                return Resp(500, {"error": {"message": "errore interno"}})
            start = int(headers["Range"].split("=")[1].rstrip("-")) if "Range" in headers else 0
            (self.ranges.append((i, start)) if start else self.downloads.append(i))
            brk = None
            if i in self.break_once:
                self.break_once.discard(i)
                brk = 3000
            return Resp(206 if start else 200, content=self.items[i]["content"][start:], break_after=brk)
        return Resp(404, {"error": {"message": f"non trovato {url}"}})
