from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import re
import time
import os
from db.models import db, Section

app = Flask(__name__)
CORS(app)

# Clé API OpenAI (à remplacer par une variable d'environnement en production)
openai.api_key = ""

# Chemins relatifs vers les fichiers partagés
CMD_FILE = "../shared_commands/commands.txt"
LOCKFILE = "../shared_commands/commands.lock"
LOG_FILE = "../shared_commands/terminal.log"


@app.route("/sections", methods=["POST"])
def create_section():
    data = request.get_json()
    user_id = data.get("user_id")
    context = data.get("context")

    if not user_id or not context:
        return jsonify({"error": "user_id and context are required"}), 400

    try:
        from db.models import Section, db  # au cas où ce n'est pas déjà importé en haut

        section = Section(user_id=user_id, context=context)
        db.session.add(section)
        db.session.commit()

        return jsonify({
            "message": "Section created successfully",
            "section": {
                "id": section.id,
                "context": section.context,
                "created_at": section.created_at.isoformat(),
                "user_id": section.user_id
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/sections", methods=["GET"])
def get_sections():
    try:
        sections = Section.query.all()
        data = [
            {
                "id": section.id,
                "context": section.context,
                "created_at": section.created_at.isoformat(),
                "user_id": section.user_id
            }
            for section in sections
        ]
        return jsonify({"sections": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




def extract_shell_commands(text):
    """Extrait les commandes shell à partir des blocs de code bash/shell."""
    code_lines = []
    code_blocks = re.findall(r"```(?:bash|shell)?\n(.*?)```", text, re.DOTALL)

    for block in code_blocks:
        lines = block.strip().split('\n')
        for line in lines:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith("#"):
                clean_line = re.sub(r"^[\$#]\s*", "", clean_line)
                code_lines.append(clean_line)

    return list(dict.fromkeys([line for line in code_lines if line]))

def wait_for_lock_release():
    """Attend que le programme C ait supprimé le lock"""
    while os.path.exists(LOCKFILE):
        time.sleep(1)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    prompt = data.get("prompt")

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    try:
        # Demander à GPT-4 de générer les commandes shell
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es AVA, une assistante vocale intelligente. "
                        "Quand je te demande d'exécuter ou faire quelque chose, renvoie-moi "
                        "juste les commandes shell dans un bloc de code unique en bash. "
                        "si tu doit ecrire dans un fichier tu doit faire plusieur ligne avec echo"
                        "Sinon, réponds simplement comme une assistante vocale."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        message = response.choices[0].message.content
        shell_commands = extract_shell_commands(message)

        # 1. Attendre que le programme C ait terminé avec le précédent lock
        wait_for_lock_release()

        # 2. Écrire les commandes dans le fichier
        with open(CMD_FILE, "w") as f:
            for cmd in shell_commands:
                f.write(cmd + "\n")

        # 3. Créer le lock une fois prêt
        with open(LOCKFILE, "w") as f:
            f.write("locked")
        
        with open(LOG_FILE, "a") as f:
            for cmd in shell_commands:
                f.write(f"> {cmd}\n")

        return jsonify({"response": message, "code_lines": shell_commands})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear-logs", methods=["POST"])
def clear_logs():
    """Vider le fichier de logs."""
    try:
        with open(LOG_FILE, "w") as f:
            f.write("")  # Vide le fichier
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/run-command", methods=["POST"])
def run_command():
    data = request.json
    command = data.get("command")
    if not command:
        return jsonify({"error": "No command provided"}), 400

    try:
        wait_for_lock_release()

        with open(CMD_FILE, "w") as f:
            f.write(command.strip() + "\n")

        with open(LOCKFILE, "w") as f:
            f.write("locked")

        # Ajout d'un séparateur unique dans le fichier log (optionnel)
        with open(LOG_FILE, "a") as f:
            f.write("\n")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/logs", methods=["GET"])
def get_logs():
    """Retourner le contenu du fichier terminal.log"""
    try:
        if not os.path.exists(LOG_FILE):
            return jsonify({"error": "Log file not found"}), 404
        with open(LOG_FILE, "r") as f:
            logs = f.read()
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    try:
        with open(LOG_FILE, "w") as f:
            f.write("=== Nouveau démarrage du serveur Flask ===\n")
        print(f"Fichier log {LOG_FILE} réinitialisé.")
    except Exception as e:
        print(f"Erreur lors de la réinitialisation du log : {e}")

    app.run(port=5000)


