
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CHARACTER_FILE = BASE_DIR / "character.json"
MAPPING_FILE = BASE_DIR / "answer_to_features.json"

# 総合スコアの重み（合計100%）
WEIGHTS = {
    "personality": 0.50,  # Q1～Q5
    "height": 0.20,       # Q6
    "other": 0.30,        # Q7～Q10
}

HEIGHT_ANSWERS = {
    "高身長（175cm以上）": "high",
    "中背（170〜174cm）": "middle",
    "低身長（169cm以下）": "low",
}

QUESTION_GROUPS = {
    "personality": [
        "Q1_好きな性格",
        "Q2_惹かれる一面",
        "Q3_好きな雰囲気",
        "Q4_惹かれる行動",
        "Q5_気になるタイプ",
    ],
    "other": [
        "Q7_好きな趣味",
        "Q8_好きな特技",
        "Q9_気になる活動",
        "Q10_惹かれる目標",
    ],
}


def load_json(path):
    """JSONファイルを読み込む。"""
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} が見つかりません。\n"
            "recommend.py と同じフォルダに置いてください。"
        )

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_field_text(character, field_paths):
    """対応表で指定されたフィールドを検索用の文字列にまとめる。"""
    values = []

    for path in field_paths:
        value = character

        for key in path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break

        if isinstance(value, list):
            values.extend(
                str(item) for item in value if item is not None
            )
        elif value is not None:
            values.append(str(value))

    return " ".join(values)


def get_height_category(height_text):
    """身長を3段階に分類する。"""
    match = re.search(r"\d+(?:\.\d+)?", str(height_text))

    if not match:
        return None

    height = float(match.group())

    if height >= 175:
        return "high"
    if height >= 170:
        return "middle"

    return "low"


def ask_answers(mapping):
    """質問を順番に表示し、ユーザーの回答を受け取る。"""
    answers = {}

    print("\nキャラクターの好みを10問で診断します！")
    print("各質問で番号を1つ選んでください。\n")

    for question_id, options in mapping["answer_to_features"].items():
        print(f"\n【{question_id}】")
        option_list = list(options.keys())

        for i, option in enumerate(option_list, start=1):
            print(f"  {i}. {option}")

        while True:
            raw = input("番号を入力してください: ").strip()

            if raw.isdigit() and 1 <= int(raw) <= len(option_list):
                answers[question_id] = option_list[int(raw) - 1]
                break

            print(f"1〜{len(option_list)} の番号を入力してください。")

    return answers


def score_keyword_question(character, question_id, answer, mapping):
    """1つの質問のキーワード一致率を計算する。"""
    keywords = mapping["answer_to_features"][question_id][answer]
    fields = mapping["field_mapping"][question_id]
    text = get_field_text(character, fields)

    matched = []

    for keyword in keywords:
        if keyword and keyword in text and keyword not in matched:
            matched.append(keyword)

    if not keywords:
        return 0.0, matched

    return len(matched) / len(keywords), matched


def calculate_scores(characters, answers, mapping):
    """キャラクターごとの性格・身長・その他・総合スコアを計算する。"""
    results = []

    for character in characters:
        personality_scores = []
        other_scores = []
        personality_evidence = []
        other_evidence = []

        # Q1～Q5：性格に関するスコア
        for question_id in QUESTION_GROUPS["personality"]:
            answer = answers[question_id]

            score, matched = score_keyword_question(
                character, question_id, answer, mapping
            )

            personality_scores.append(score)
            personality_evidence.extend(matched)

        # Q7～Q10：趣味・特技・活動・目標に関するスコア
        for question_id in QUESTION_GROUPS["other"]:
            answer = answers[question_id]

            # 「特にこだわりはない」は加点対象にしない
            if answer == "特にこだわりはない":
                continue

            score, matched = score_keyword_question(
                character, question_id, answer, mapping
            )

            other_scores.append(score)
            other_evidence.extend(matched)

        personality_score = (
            sum(personality_scores) / len(personality_scores)
            if personality_scores else 0.0
        )

        other_score = (
            sum(other_scores) / len(other_scores)
            if other_scores else 0.0
        )

        # Q6：身長スコア
        height_answer = answers["Q6_身長"]

        if height_answer == "特にこだわりはない":
            height_score = None
        else:
            preferred = HEIGHT_ANSWERS[height_answer]

            actual = get_height_category(
                character.get("basic_profile", {}).get("height", "")
            )

            height_score = 1.0 if actual == preferred else 0.0

        # 回答した項目だけで重みを再調整する
        weighted_total = personality_score * WEIGHTS["personality"]
        total_weight = WEIGHTS["personality"]

        if height_score is not None:
            weighted_total += height_score * WEIGHTS["height"]
            total_weight += WEIGHTS["height"]

        weighted_total += other_score * WEIGHTS["other"]
        total_weight += WEIGHTS["other"]

        overall_score = (
            weighted_total / total_weight if total_weight else 0.0
        )

        results.append({
            "character": character,
            "personality_score": personality_score,
            "height_score": height_score,
            "other_score": other_score,
            "overall_score": overall_score,
            "personality_evidence": list(dict.fromkeys(personality_evidence)),
            "other_evidence": list(dict.fromkeys(other_evidence)),
        })

    return results


def print_ranking(title, results, score_key, top_n=5):
    """指定されたスコアで上位キャラクターを表示する。"""
    ranked = sorted(
        results,
        key=lambda item: item[score_key],
        reverse=True
    )

    print(f"\n{'=' * 48}")
    print(title)
    print("=" * 48)

    for rank, item in enumerate(ranked[:top_n], start=1):
        character = item["character"]
        score = item[score_key] * 100

        height = character.get("basic_profile", {}).get("height", "不明")

        print(
            f"{rank}位：{character['name']} "
            f"（{character.get('unit', '所属不明')}）"
        )
        print(f"    スコア：{score:.1f}点 / 100点")
        print(f"    身長：{height}")

        if score_key == "personality_score":
            evidence = item["personality_evidence"]
        else:
            evidence = list(dict.fromkeys(
                item["personality_evidence"]
                + item["other_evidence"]
            ))

        if evidence:
            print(f"    一致したキーワード：{', '.join(evidence[:6])}")

        print()


def main():
    try:
        characters = load_json(CHARACTER_FILE)
        mapping = load_json(MAPPING_FILE)

    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"ファイル読み込みエラー：{error}")
        return

    print(f"キャラクター数：{len(characters)}人")

    answers = ask_answers(mapping)
    results = calculate_scores(characters, answers, mapping)

    # 性格重視ランキング
    print_ranking(
        "性格重視のおすすめ TOP 5",
        results,
        "personality_score"
    )

    # 総合ランキング
    print_ranking(
        "総合おすすめ TOP 5",
        results,
        "overall_score"
    )

    print("診断が終了しました！")


if __name__ == "__main__":
    main()
