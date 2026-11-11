from pathlib import Path

from flask import Flask, render_template, request

from recommend import calculate_scores, load_json


BASE_DIR = Path(__file__).resolve().parent

CHARACTER_FILE = BASE_DIR / "character.json"
MAPPING_FILE = BASE_DIR / "answer_to_features.json"

app = Flask(__name__)


def get_data():
    """診断に必要なJSONデータを読み込む。"""
    characters = load_json(CHARACTER_FILE)
    mapping = load_json(MAPPING_FILE)

    return characters, mapping


def make_ranking(results, score_key, ranking_type):
    """ランキング表示用のデータを作る。"""

    ranked = sorted(
        results,
        key=lambda item: item[score_key],
        reverse=True
    )

    output = []

    for rank, item in enumerate(ranked[:5], start=1):
        character = item["character"]

        if ranking_type == "personality":
            evidence = item["personality_evidence"]
        else:
            evidence = list(dict.fromkeys(
                item["personality_evidence"]
                + item["other_evidence"]
            ))

        output.append({
            "rank": rank,
            "name": character.get("name", "名前不明"),
            "unit": character.get("unit", "所属不明"),
            "height": character.get(
                "basic_profile", {}
            ).get("height", "不明"),
            "score": round(item[score_key] * 100, 1),
            "evidence": evidence[:6],
        })

    return output


@app.route("/")
def index():
    """10問の診断画面を表示する。"""

    try:
        characters, mapping = get_data()

        questions = mapping["answer_to_features"]

        return render_template(
            "index.html",
            questions=questions,
            character_count=len(characters)
        )

    except (FileNotFoundError, KeyError, ValueError) as error:
        return render_template(
            "index.html",
            questions={},
            character_count=0,
            error_message=str(error)
        ), 500


@app.route("/diagnose", methods=["POST"])
def diagnose():
    """回答を受け取り、Pythonで診断する。"""

    try:
        characters, mapping = get_data()

        questions = mapping["answer_to_features"]

        # HTMLから送られた回答を取得
        answers = {}

        for question_id, options in questions.items():
            answer = request.form.get(question_id)

            # 未回答・不正な選択肢をチェック
            if answer not in options:
                return render_template(
                    "index.html",
                    questions=questions,
                    character_count=len(characters),
                    error_message=f"{question_id} の回答を確認してください。"
                ), 400

            answers[question_id] = answer

        # 既存のPythonの診断ロジックを実行
        results = calculate_scores(
            characters,
            answers,
            mapping
        )

        # 既存と同じ2種類のランキングを作成
        personality_ranking = make_ranking(
            results,
            "personality_score",
            "personality"
        )

        overall_ranking = make_ranking(
            results,
            "overall_score",
            "overall"
        )

        return render_template(
            "result.html",
            personality_ranking=personality_ranking,
            overall_ranking=overall_ranking,
            character_count=len(characters)
        )

    except (FileNotFoundError, KeyError, ValueError) as error:
        return f"診断エラー：{error}", 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
