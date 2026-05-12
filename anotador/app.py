"""
Anotador local rápido para el bono de modismos colombianos.
Sustituye Label Studio para esta tarea específica con atajos de teclado.

Uso:
    pip install flask
    python download_images.py   # primero descarga las imágenes
    python app.py               # luego abre http://localhost:5000
"""
import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask, abort, jsonify, redirect, render_template,
    request, send_file, send_from_directory, url_for,
)

ROOT = Path(__file__).parent
PARENT = ROOT.parent
DB_PATH = ROOT / "annotations.db"
IMG_DIR = ROOT / "images"
URL_MAP_PATH = ROOT / "url_map.json"

SINGLE_CSV = PARENT / "SingleLabelStudioGPT_JorgeDavidBustamantePino.csv"
MULTI_CSV = PARENT / "MultiLabelStudioGEMINI_JorgeDavidBustamantePino.csv"

app = Flask(__name__)


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


SINGLE_TASKS = load_csv(SINGLE_CSV)
MULTI_TASKS = load_csv(MULTI_CSV)
URL_MAP: dict[str, str] = {}
if URL_MAP_PATH.exists():
    URL_MAP = json.loads(URL_MAP_PATH.read_text(encoding="utf-8"))

SINGLE_BY_ID = {t["id_modismo"]: (i, t) for i, t in enumerate(SINGLE_TASKS)}
MULTI_BY_ID = {t["id_modismo"]: (i, t) for i, t in enumerate(MULTI_TASKS)}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS annotations_single (
            id_modismo TEXT PRIMARY KEY,
            evaluacion_binaria TEXT,
            no_es_modismo INTEGER DEFAULT 0,
            otro_significado TEXT,
            comentarios TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS annotations_multi (
            id_modismo TEXT PRIMARY KEY,
            clasif_1 TEXT, clasif_2 TEXT, clasif_3 TEXT, clasif_4 TEXT,
            rank_1 INTEGER, rank_2 INTEGER, rank_3 INTEGER, rank_4 INTEGER,
            no_es_modismo INTEGER DEFAULT 0,
            no_es_doble_sentido INTEGER DEFAULT 0,
            comentarios TEXT,
            updated_at TEXT
        );
        """)


init_db()


def img_url_for(remote_url: str) -> str:
    """Devuelve URL local si la imagen está descargada, o el URL remoto como fallback."""
    if not remote_url:
        return ""
    fname = URL_MAP.get(remote_url)
    if fname and (IMG_DIR / fname).exists():
        return url_for("serve_image", filename=fname)
    return remote_url


def is_annotated_single(row: sqlite3.Row | None) -> bool:
    if row is None:
        return False
    if row["evaluacion_binaria"] in ("Sí", "No"):
        return True
    if row["no_es_modismo"]:
        return True
    return False


def is_annotated_multi(row: sqlite3.Row | None) -> bool:
    if row is None:
        return False
    if row["no_es_modismo"] or row["no_es_doble_sentido"]:
        return True
    classifs = [row[f"clasif_{i}"] for i in range(1, 5)]
    ranks = [row[f"rank_{i}"] for i in range(1, 5)]
    return all(classifs) and all(ranks)


def get_progress():
    with db() as conn:
        single_rows = {r["id_modismo"]: r for r in conn.execute("SELECT * FROM annotations_single")}
        multi_rows = {r["id_modismo"]: r for r in conn.execute("SELECT * FROM annotations_multi")}
    single_done = sum(1 for t in SINGLE_TASKS if is_annotated_single(single_rows.get(t["id_modismo"])))
    multi_done = sum(1 for t in MULTI_TASKS if is_annotated_multi(multi_rows.get(t["id_modismo"])))
    return {
        "single_done": single_done,
        "single_total": len(SINGLE_TASKS),
        "multi_done": multi_done,
        "multi_total": len(MULTI_TASKS),
    }


@app.route("/")
def index():
    return render_template("index.html", progress=get_progress())


@app.route("/img/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMG_DIR, filename)


# ---------------- SINGLE ----------------

@app.route("/single")
def single_next():
    with db() as conn:
        rows = {r["id_modismo"]: r for r in conn.execute("SELECT * FROM annotations_single")}
    for i, t in enumerate(SINGLE_TASKS):
        if not is_annotated_single(rows.get(t["id_modismo"])):
            return redirect(url_for("single_task", idx=i))
    return redirect(url_for("index"))


@app.route("/single/<int:idx>")
def single_task(idx):
    if not 0 <= idx < len(SINGLE_TASKS):
        abort(404)
    task = SINGLE_TASKS[idx]
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM annotations_single WHERE id_modismo = ?",
            (task["id_modismo"],),
        ).fetchone()
    annotation = dict(row) if row else {}
    return render_template(
        "single.html",
        task=task,
        idx=idx,
        total=len(SINGLE_TASKS),
        image_src=img_url_for(task["image"]),
        annotation=annotation,
        progress=get_progress(),
    )


@app.route("/api/single/<id_modismo>", methods=["POST"])
def save_single(id_modismo):
    if id_modismo not in SINGLE_BY_ID:
        abort(404)
    data = request.get_json(force=True)
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute("""
            INSERT INTO annotations_single
                (id_modismo, evaluacion_binaria, no_es_modismo, otro_significado, comentarios, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_modismo) DO UPDATE SET
                evaluacion_binaria=excluded.evaluacion_binaria,
                no_es_modismo=excluded.no_es_modismo,
                otro_significado=excluded.otro_significado,
                comentarios=excluded.comentarios,
                updated_at=excluded.updated_at
        """, (
            id_modismo,
            data.get("evaluacion_binaria") or None,
            1 if data.get("no_es_modismo") else 0,
            (data.get("otro_significado") or "").strip() or None,
            (data.get("comentarios") or "").strip() or None,
            now,
        ))
    return jsonify({"ok": True, "progress": get_progress()})


# ---------------- MULTI ----------------

@app.route("/multi")
def multi_next():
    with db() as conn:
        rows = {r["id_modismo"]: r for r in conn.execute("SELECT * FROM annotations_multi")}
    for i, t in enumerate(MULTI_TASKS):
        if not is_annotated_multi(rows.get(t["id_modismo"])):
            return redirect(url_for("multi_task", idx=i))
    return redirect(url_for("index"))


@app.route("/multi/<int:idx>")
def multi_task(idx):
    if not 0 <= idx < len(MULTI_TASKS):
        abort(404)
    task = MULTI_TASKS[idx]
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM annotations_multi WHERE id_modismo = ?",
            (task["id_modismo"],),
        ).fetchone()
    annotation = dict(row) if row else {}
    return render_template(
        "multi.html",
        task=task,
        idx=idx,
        total=len(MULTI_TASKS),
        images=[img_url_for(task[f"img_{i}"]) for i in range(1, 5)],
        annotation=annotation,
        progress=get_progress(),
    )


@app.route("/api/multi/<id_modismo>", methods=["POST"])
def save_multi(id_modismo):
    if id_modismo not in MULTI_BY_ID:
        abort(404)
    data = request.get_json(force=True)
    now = datetime.now(timezone.utc).isoformat()

    def _rank(v):
        if v in (None, "", "null"):
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    with db() as conn:
        conn.execute("""
            INSERT INTO annotations_multi
                (id_modismo, clasif_1, clasif_2, clasif_3, clasif_4,
                 rank_1, rank_2, rank_3, rank_4,
                 no_es_modismo, no_es_doble_sentido, comentarios, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_modismo) DO UPDATE SET
                clasif_1=excluded.clasif_1, clasif_2=excluded.clasif_2,
                clasif_3=excluded.clasif_3, clasif_4=excluded.clasif_4,
                rank_1=excluded.rank_1, rank_2=excluded.rank_2,
                rank_3=excluded.rank_3, rank_4=excluded.rank_4,
                no_es_modismo=excluded.no_es_modismo,
                no_es_doble_sentido=excluded.no_es_doble_sentido,
                comentarios=excluded.comentarios,
                updated_at=excluded.updated_at
        """, (
            id_modismo,
            data.get("clasif_1") or None, data.get("clasif_2") or None,
            data.get("clasif_3") or None, data.get("clasif_4") or None,
            _rank(data.get("rank_1")), _rank(data.get("rank_2")),
            _rank(data.get("rank_3")), _rank(data.get("rank_4")),
            1 if data.get("no_es_modismo") else 0,
            1 if data.get("no_es_doble_sentido") else 0,
            (data.get("comentarios") or "").strip() or None,
            now,
        ))
    return jsonify({"ok": True, "progress": get_progress()})


# ---------------- EXPORT ----------------

def _ls_choice(value: str | None) -> str:
    """Choices con 1 valor → string pelado (formato Label Studio CSV real)."""
    if not value:
        return ""
    return value


def _ls_choices_multi(values: list[str]) -> str:
    """Choices con N valores: 1 → string, N>1 → lista JSON."""
    values = [v for v in values if v]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return json.dumps(values, ensure_ascii=False)


def _ls_textarea(value: str | None) -> str:
    """TextArea con 1 valor → string pelado."""
    if not value:
        return ""
    return value


@app.route("/export/single")
def export_single():
    with db() as conn:
        rows = {r["id_modismo"]: r for r in conn.execute("SELECT * FROM annotations_single")}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "id_modismo", "modismo", "significado", "image",
        "evaluacion_binaria", "no_es_modismo", "otro_significado", "comentarios",
        "annotated_at",
    ])
    for t in SINGLE_TASKS:
        a = rows.get(t["id_modismo"])
        w.writerow([
            t["id_modismo"], t["modismo"], t["significado"], t["image"],
            _ls_choice(a["evaluacion_binaria"]) if a else "",
            _ls_choices_multi(["Esta expresión NO es un modismo colombiano"]) if a and a["no_es_modismo"] else "",
            _ls_textarea(a["otro_significado"]) if a else "",
            _ls_textarea(a["comentarios"]) if a else "",
            a["updated_at"] if a else "",
        ])
    data = out.getvalue().encode("utf-8-sig")
    return send_file(
        io.BytesIO(data),
        mimetype="text/csv",
        as_attachment=True,
        download_name="SingleLabelStudioGPT_JorgeDavidBustamantePino_anotado.csv",
    )


@app.route("/export/multi")
def export_multi():
    with db() as conn:
        rows = {r["id_modismo"]: r for r in conn.execute("SELECT * FROM annotations_multi")}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "id_modismo", "modismo", "significado", "ejemplo",
        "img_1", "img_2", "img_3", "img_4",
        "clasif_1", "clasif_2", "clasif_3", "clasif_4",
        "rank_1", "rank_2", "rank_3", "rank_4",
        "casos_especiales", "comentarios",
        "annotated_at",
    ])
    for t in MULTI_TASKS:
        a = rows.get(t["id_modismo"])
        casos = []
        if a and a["no_es_modismo"]:
            casos.append("Esta expresión NO es un modismo colombiano")
        if a and a["no_es_doble_sentido"]:
            casos.append("Esta expresión es un modismo, pero NO es de doble sentido")
        w.writerow([
            t["id_modismo"], t["modismo"], t["significado"], t["ejemplo"],
            t["img_1"], t["img_2"], t["img_3"], t["img_4"],
            _ls_choice(a["clasif_1"]) if a else "",
            _ls_choice(a["clasif_2"]) if a else "",
            _ls_choice(a["clasif_3"]) if a else "",
            _ls_choice(a["clasif_4"]) if a else "",
            _ls_choice(str(a["rank_1"])) if a and a["rank_1"] else "",
            _ls_choice(str(a["rank_2"])) if a and a["rank_2"] else "",
            _ls_choice(str(a["rank_3"])) if a and a["rank_3"] else "",
            _ls_choice(str(a["rank_4"])) if a and a["rank_4"] else "",
            _ls_choices_multi(casos),
            _ls_textarea(a["comentarios"]) if a else "",
            a["updated_at"] if a else "",
        ])
    data = out.getvalue().encode("utf-8-sig")
    return send_file(
        io.BytesIO(data),
        mimetype="text/csv",
        as_attachment=True,
        download_name="MultiLabelStudioGEMINI_JorgeDavidBustamantePino_anotado.csv",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
