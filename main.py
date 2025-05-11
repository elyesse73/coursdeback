from ast import alias
from operator import is_
from uuid import uuid4
from fastapi import Cookie, FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket
from typing import List
from time import time_ns

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*", "http://localhost:8000"], allow_credentials=True
)


class UserInfo:
    last_edited_time_nanos: int
    last_seen_map: list[list[tuple(int, int, int)]]

    def __init__(self, carte):
        self.last_seen_map = deepcopy(carte)
        self.last_edited_time_nanos = 0


class Carte:
    keys: set[str]
    users: dict[str, UserInfo]
    nx: int
    ny: int
    data: list[list[tuple(int, int, int)]]
    timeout_nanos: int

    def __init__(self, nx: int, ny: int, timeout_nanos: int = 10**10):
        self.keys = set()
        self.users = {}
        self.nx = nx
        self.ny = ny
        self.data = [[(0, 0, 0) for _ in range(ny)] for _ in range(nx)]
        self.timeout_nanos = timeout_nanos

    def create_new_key(self):
        key = str(uuid4())
        self.keys.add(key)
        return key

    def is_valid_key(self, key: str):
        return key in self.keys

    def create_new_user_id(self):
        user_id = str(uuid4())
        self.users[user_id] = UserInfo(self.data)
        return user_id

    def is_valid_user_id(self, user_id: str):
        return user_id in self.user_ids


cartes: dict[str, Carte] = {"0000": Carte(nx=100, ny=100)}


@app.get("/api/v1/{nom_carte}/preinit")
async def preinit(nom_carte: str):
    if not nom_carte in cartes:
        return {"error": "Je n'ai pas trouvé la carte."}
    key = cartes[nom_carte].create_new_key()
    res = JSONResponse({"key": key})
    res.set_cookie("key", key, secure=True, samesite="none", max_age=3600)
    return res


@app.get("/api/v1/{nom_carte}/init")
async def init(
    nom_carte: str,
    query_key: str = Query(alias="key"),
    cookie_key: str = Cookie(alias="key"),
):
    carte = cartes[nom_carte]
    if not nom_carte in cartes:
        return {"error": "Je n'ai pas trouvé la carte."}
    if query_key != cookie_key:
        return {"error": "Les clés ne correspondent pas."}
    if not carte.is_valid_key(cookie_key):
        return {"error": "La clé n'est pas valide."}
    user_id = carte.create_new_user_id()
    res = JSONResponse(
        {"id": user_id, "nx": carte.nx, "ny": carte.nx, "data": carte.data}
    )
    return res


@app.get("/api/v1/{nom_carte}/deltas")
async def deltas(
    nom_carte: str,
    query_user_id: str = Query(alias="id"),
    cookie_key: str = Cookie(alias="key"),
    cookie_user_id: str = Cookie(alias="id"),
):
    carte = cartes[nom_carte]
    if carte is None:
        return {"error": "Je n'ai pas trouvé la carte."}
    if not carte.is_valid_key(cookie_key):
        return {"error": "La clé n'est pas valide."}
    if query_user_id != cookie_user_id:
        return {"error": "Les identifiants utilisateur ne correspondent pas."}
    if not carte.is_valid_user_id(query_user_id):
        return {"error": "L'id utilisateur n'est pas valide."}
    user_info = carte.users[query_user_id]
    user_carte = user_info.last_seen_map
    deltas: list[tuple(int, int, int, int, int)] = []
    for y in range(carte.ny):
        for x in range(carte.nx):
            if carte.data[x][y] != user_carte[x][y]:
                r, g, b = carte.data[x][y]
                deltas.append((y, x, r, g, b))
                user_carte[x][y] = carte.data[x][y]
    return JSONResponse(
        {
            "id": query_user_id,
            "nx": carte.nx,
            "ny": carte.ny,
            "timeout": carte.timeout_nanos,
            "deltas": deltas,
        }
    )
## --- Code vu en cours --- ##
# Il y a des imports supplémentaires, mais pas de modification de classes ou de fonctions (si ma mémoire est bonne)


## Modification des pixels par l'utilisateur

@app.post("/api/v1/{nom_carte}/update_pixel")
async def update_pixel(
    nom_carte: str,
    x: int = Query(...),
    y: int = Query(...),
    r: int = Query(...),
    g: int = Query(...),
    b: int = Query(...),
    cookie_key: str = Cookie(alias="key"),
    cookie_user_id: str = Cookie(alias="id"),
):
    # Vérification des identifiants et des paramètres donnés par l'utilisateur
    carte = cartes.get(nom_carte)
    if not carte:
        raise HTTPException(status_code=404, detail="Carte introuvable.")
    if not carte.is_valid_key(cookie_key):
        raise HTTPException(status_code=403, detail="Clé invalide.")
    if not carte.is_valid_user_id(cookie_user_id):
        raise HTTPException(status_code=403, detail="ID utilisateur invalide.")
    if not (0 <= x < carte.nx and 0 <= y < carte.ny):
        raise HTTPException(status_code=400, detail="Coordonnées hors limites.")
    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
        raise HTTPException(status_code=400, detail="Valeurs RGB invalides.")

    # On récupère les données de l'utilisateur ...
    user_info = carte.users[cookie_user_id]

    # et on vérifie si l'utilisateur a le droit de modifier le pixel
    current_time_nanos = time_ns()
    if current_time_nanos - user_info.last_edited_time_nanos < carte.timeout_nanos:
        remaining_time = (carte.timeout_nanos - (current_time_nanos - user_info.last_edited_time_nanos)) / 1e9
        raise HTTPException(
            status_code=429,
            detail=f"Vous devez attendre encore {remaining_time:.1f} secondes avant de mettre à jour un autre pixel.",
        )

    # Mise à jour du pixel ...
    new_pixel = (r, g, b)
    carte.data[x][y] = new_pixel

    # et des informations de l'utilisateur
    user_info.last_seen_map[x][y] = new_pixel
    user_info.last_edited_time_nanos = current_time_nanos

    # On prépare la mise à jour à envoyer aux autres utilisateurs
    delta = (y, x, r, g, b)

    # et on utilise la liste des connexions actives pour envoyer la mise à jour
    for connection in active_connections:
        try:
            await connection.send_json({"type": "update", "delta": delta})
        except:
            active_connections.remove(connection)

    return {"message": "Pixel mis à jour avec succès."}

## Mise à jour de la carte pour l'utilisateur en temps réel

active_connections: List[WebSocket] = []

@app.websocket("/ws/{nom_carte}")
async def websocket_endpoint(websocket: WebSocket, nom_carte: str):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Tant que l'utilisateur est connecté
            await websocket.receive_text()
    except:
        active_connections.remove(websocket)