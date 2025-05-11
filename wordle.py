from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from uuid import uuid4
import random

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True
)

# Liste prédéfinie de mots valides (pour simplifier, on utilise une liste fixe ici)
VALID_WORDS = [
    "arbre", "balai", "carte", "drape", "ecran", 
    "fleur", "glace", "hiver", "jouer", "livre", 
    "monde", "neige", "ombre", "plage", "quand", 
    "rêver", "sable", "table", "utile", "vague"
]
SECRET_WORD = random.choice(VALID_WORDS)  # On joue avec un mot secret aléatoire
MAX_ATTEMPTS = 6

# On stocke l'état des jeux en cours, bien sûr, dans une vraie application, on utiliserait une base de données
# mais je ne sais pas faire et j'ai pas trop le temps pour le moment
games = {}

# Une classe pour représenter un jeu, j'ai pas fait Python avancé donc c'est pas très étayé (#C++)

class Game:
    def __init__(self, secret_word: str):
        self.secret_word = secret_word
        self.attempts = []
        self.is_over = False

# On démarre un nouveau jeu, avec un mot secret et d'autres paramètres, 
# et on renvoie une clé de jeu unique, de la même manière que pour les pixel wars

@app.post("/api/v1/start")
async def start_game():
    game_id = str(uuid4())
    games[game_id] = Game(secret_word=SECRET_WORD)
    return {"game_id": game_id, "max_attempts": MAX_ATTEMPTS, "word_length": len(SECRET_WORD)}

# On joue, on essaie de deviner un mot

@app.post("/api/v1/{game_id}/guess")
async def make_guess(game_id: str, guess: str = Query(...)):

    # On réalise les vérifications habituelles et on évite les erreurs
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found.")
    
    game = games[game_id]
    if game.is_over:
        raise HTTPException(status_code=400, detail="Game is already over.")
    
    if len(guess) != len(game.secret_word):
        raise HTTPException(status_code=400, detail="Invalid guess length.")
    
    if guess not in VALID_WORDS:
        raise HTTPException(status_code=400, detail="Invalid word.")
    
    # Roulemenent de tambour ... on vérifie la réponse et ...
    feedback = []
    for i, char in enumerate(guess):
        if char == game.secret_word[i]:
            feedback.append("correct")
        elif char in game.secret_word:
            feedback.append("present")
        else:
            feedback.append("absent")
    
    # on indique quelles lettres sont correctes, présentes ou absentes
    game.attempts.append({"guess": guess, "feedback": feedback})
    
    if guess == game.secret_word:
        game.is_over = True
        return {"message": "Bien joué, vous avez deviné le mot!", "feedback": feedback, "attempts": game.attempts}
    
    if len(game.attempts) >= MAX_ATTEMPTS:
        game.is_over = True
        return {"message": "Trop de tentatives. Vous avez échoué", "secret_word": game.secret_word}
    
    return {"feedback": feedback, "remaining_attempts": MAX_ATTEMPTS - len(game.attempts)}

# Les informations sur le jeu, comme le nombre d'essais restants, qu'on pourrait afficher sur une page web ou dans une application mobile
@app.get("/api/v1/{game_id}/status")
async def game_status(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found.")
    
    game = games[game_id]
    return {
        "attempts": game.attempts,
        "is_over": game.is_over,
        "remaining_attempts": MAX_ATTEMPTS - len(game.attempts),
    }

# N'étant pas un joueur assidu de Wordle (0 parties jouées à mon actif), je ne sais pas quelles fonctionnalités seraient les plus 
# pertinentes à ajouter
# Un mode multijoueur, ou le choix de la difficulté ? Par exemple, en décidant de la longueur du mot secret, ou en ajoutant une limite de
# temps pour chaque essai
# On peut imaginer plein de choses, mais je vais m'arrêter là pour l'instant, 
# peut-être que je m'attelerai au frontend du projet avant la date limite, mais je ne promets rien