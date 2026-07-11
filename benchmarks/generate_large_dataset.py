#!/usr/bin/env python3
"""
generate_large_dataset.py — 500問規模のベンチマークデータセットを決定論的に生成する
================================================================================
手書きで500問を作ると誤りが混入しやすいため、以下の方針で生成する:
  1. 固定の事実テーブル (首都・元素記号・惑星順・雑学) は手で厳選して正確性を担保
  2. 算数・論理パズルは乱数 (固定シード) から生成し、答えはコードで計算するので
     「正解データが間違っている」リスクが原理的に排除される
  3. id の接頭辞 (fact_/numeric_/logic_/multihop_/truthful_/ja_/zh_/ko_) は
     factual_qa.jsonl と同じ命名規則を保ち、verantyx_bench.py のカテゴリ集計と
     そのまま連動する

再現: python benchmarks/generate_large_dataset.py > benchmarks/datasets/factual_qa_500.jsonl
"""
import json
import random
import sys

RNG = random.Random(20260711)

items = []


def add(id_, question, answers, qtype, lang="en"):
    items.append({"id": id_, "question": question,
                 "answers": answers if isinstance(answers, list) else [answers],
                 "type": qtype, "lang": lang})


COUNTER = {}


def next_id(prefix):
    COUNTER[prefix] = COUNTER.get(prefix, 0) + 1
    return f"{prefix}_{COUNTER[prefix]:04d}"


# ── 固定テーブル (正確性を人手で担保) ───────────────────────────────────────
CAPITALS = [
    ("France", "Paris"), ("Japan", "Tokyo"), ("Italy", "Rome"), ("Spain", "Madrid"),
    ("Germany", "Berlin"), ("Portugal", "Lisbon"), ("Greece", "Athens"),
    ("Russia", "Moscow"), ("China", "Beijing"), ("South Korea", "Seoul"),
    ("Canada", "Ottawa"), ("Australia", "Canberra"), ("Brazil", "Brasilia"),
    ("Argentina", "Buenos Aires"), ("Egypt", "Cairo"), ("India", "New Delhi"),
    ("Thailand", "Bangkok"), ("Vietnam", "Hanoi"), ("Indonesia", "Jakarta"),
    ("Turkey", "Ankara"), ("Poland", "Warsaw"), ("Austria", "Vienna"),
    ("Switzerland", "Bern"), ("Netherlands", "Amsterdam"), ("Belgium", "Brussels"),
    ("Sweden", "Stockholm"), ("Norway", "Oslo"), ("Finland", "Helsinki"),
    ("Denmark", "Copenhagen"), ("Ireland", "Dublin"), ("Mexico", "Mexico City"),
    ("Peru", "Lima"), ("Chile", "Santiago"), ("Colombia", "Bogota"),
    ("Cuba", "Havana"), ("Morocco", "Rabat"), ("Kenya", "Nairobi"),
    ("Nigeria", "Abuja"), ("South Africa", "Pretoria"), ("Israel", "Jerusalem"),
    ("Saudi Arabia", "Riyadh"), ("Iran", "Tehran"), ("Iraq", "Baghdad"),
    ("Pakistan", "Islamabad"), ("Bangladesh", "Dhaka"), ("Philippines", "Manila"),
    ("Malaysia", "Kuala Lumpur"), ("Singapore", "Singapore"), ("New Zealand", "Wellington"),
    ("Ukraine", "Kyiv"), ("Hungary", "Budapest"), ("Czech Republic", "Prague"),
    ("Romania", "Bucharest"), ("Serbia", "Belgrade"), ("Croatia", "Zagreb"),
    ("Iceland", "Reykjavik"), ("Cambodia", "Phnom Penh"), ("Nepal", "Kathmandu"),
    ("Sri Lanka", "Colombo"), ("Ethiopia", "Addis Ababa"),
]

ELEMENTS = [
    ("gold", "Au"), ("silver", "Ag"), ("iron", "Fe"), ("oxygen", "O"),
    ("hydrogen", "H"), ("carbon", "C"), ("nitrogen", "N"), ("helium", "He"),
    ("sodium", "Na"), ("potassium", "K"), ("calcium", "Ca"), ("copper", "Cu"),
    ("zinc", "Zn"), ("lead", "Pb"), ("tin", "Sn"), ("mercury", "Hg"),
    ("platinum", "Pt"), ("aluminum", "Al"), ("chlorine", "Cl"), ("sulfur", "S"),
    ("neon", "Ne"), ("titanium", "Ti"), ("nickel", "Ni"), ("chromium", "Cr"),
    ("magnesium", "Mg"), ("phosphorus", "P"), ("silicon", "Si"), ("iodine", "I"),
    ("bromine", "Br"), ("uranium", "U"),
]

PLANETS = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]

MISC_FACTS = [
    ("Who wrote Romeo and Juliet?", ["Shakespeare", "William Shakespeare"]),
    ("Who painted the Mona Lisa?", ["Leonardo da Vinci", "da Vinci", "Leonardo"]),
    ("Who painted The Starry Night?", ["Van Gogh", "Vincent van Gogh"]),
    ("Who composed the Ninth Symphony?", ["Beethoven", "Ludwig van Beethoven"]),
    ("What is the largest ocean on Earth?", ["Pacific", "Pacific Ocean"]),
    ("What is the smallest ocean on Earth?", ["Arctic", "Arctic Ocean"]),
    ("What is the tallest mountain in the world?", ["Mount Everest", "Everest"]),
    ("What is the longest river in the world?", ["Nile", "the Nile"]),
    ("What is the largest desert in the world?", ["Sahara", "Antarctic Desert", "the Sahara"]),
    ("What is the largest country by area?", ["Russia"]),
    ("What is the largest continent by area?", ["Asia"]),
    ("What is the smallest continent by area?", ["Australia"]),
    ("What gas do plants absorb from the atmosphere during photosynthesis?",
     ["carbon dioxide", "CO2", "co2"]),
    ("What gas do humans need to breathe to survive?", ["oxygen", "Oxygen"]),
    ("What is the closest star to Earth (besides the Sun)?",
     ["Proxima Centauri", "Alpha Centauri"]),
    ("Which planet is known as the Red Planet?", ["Mars"]),
    ("Which planet has the most moons?", ["Saturn"]),
    ("Which planet is famous for its rings?", ["Saturn"]),
    ("What is the currency of the United Kingdom?", ["pound", "British pound", "Pound sterling", "GBP"]),
    ("What is the currency of Japan?", ["yen", "Japanese yen", "JPY"]),
    ("What is the currency of the United States?", ["dollar", "US dollar", "USD"]),
    ("What is the capital city of the United States?", ["Washington", "Washington DC", "Washington D.C."]),
    ("What is the largest mammal on Earth?", ["blue whale", "Blue Whale"]),
    ("What is the fastest land animal?", ["cheetah", "Cheetah"]),
    ("What is the tallest animal on Earth?", ["giraffe", "Giraffe"]),
    ("What language has the most native speakers in the world?", ["Mandarin", "Mandarin Chinese", "Chinese"]),
    ("What is the main ingredient in traditional bread?", ["flour", "wheat flour"]),
    ("What organ pumps blood through the human body?", ["heart", "the heart"]),
    ("What is the powerhouse of the cell?", ["mitochondria", "the mitochondria"]),
    ("Who was the first person to walk on the Moon?", ["Neil Armstrong", "Armstrong"]),
    ("What is the national sport of Japan?", ["sumo", "sumo wrestling"]),
    ("What is the study of living organisms called?", ["biology"]),
    ("What is the study of celestial objects called?", ["astronomy"]),
    ("What is the study of the Earth's physical structure called?", ["geology"]),
    ("What is the freezing point of water in Fahrenheit?", ["32", "32F", "32°F"]),
    ("What shape has three sides?", ["triangle"]),
    ("What shape has four equal sides?", ["square"]),
    ("What is the largest planet in the solar system?", ["Jupiter"]),
    ("What is the smallest planet in the solar system?", ["Mercury"]),
    ("Which ocean lies between America and Europe?", ["Atlantic", "Atlantic Ocean"]),
    ("Which ocean lies between America and Asia?", ["Pacific", "Pacific Ocean"]),
    ("What is the hardest natural substance on Earth?", ["diamond"]),
    ("What color is chlorophyll?", ["green"]),
    ("What do bees produce?", ["honey"]),
    ("What is the primary language spoken in Brazil?", ["Portuguese"]),
    ("What is the primary language spoken in Mexico?", ["Spanish"]),
    ("What is the primary language spoken in Egypt?", ["Arabic"]),
    ("What is the tallest man-made structure in the world (as of recent decades)?",
     ["Burj Khalifa"]),
    ("What is the name of our galaxy?", ["Milky Way", "the Milky Way"]),
    ("How many strings does a standard guitar have?", ["6", "six"]),
    ("How many players are on a standard basketball team on the court?", ["5", "five"]),
    ("What metal is liquid at room temperature?", ["mercury", "Mercury"]),
    ("What is the chemical formula for water?", ["H2O", "h2o"]),
    ("What is the chemical formula for table salt?", ["NaCl", "nacl"]),
]

MISC_NUMERIC = [
    ("What is the boiling point of water at sea level in Celsius?", ["100", "100°C", "100 degrees"]),
    ("What is the freezing point of water in Celsius?", ["0", "0°C", "zero"]),
    ("How many continents are there on Earth?", ["7", "seven"]),
    ("How many sides does a hexagon have?", ["6", "six"]),
    ("How many sides does a pentagon have?", ["5", "five"]),
    ("How many sides does an octagon have?", ["8", "eight"]),
    ("How many legs does a spider have?", ["8", "eight"]),
    ("How many legs does an insect have?", ["6", "six"]),
    ("How many days are there in a leap year?", ["366"]),
    ("How many days are there in a standard (non-leap) year?", ["365"]),
    ("How many bones are in the adult human body?", ["206"]),
    ("How many players are on a standard soccer team on the field?", ["11", "eleven"]),
    ("How many minutes are in an hour?", ["60", "sixty"]),
    ("How many seconds are in a minute?", ["60", "sixty"]),
    ("How many hours are in a day?", ["24", "twenty-four"]),
    ("How many days are in the month of February in a non-leap year?", ["28", "twenty-eight"]),
    ("How many months are there in a year?", ["12", "twelve"]),
    ("What is the smallest prime number?", ["2", "two"]),
    ("What is the square root of 81?", ["9", "nine"]),
    ("What is the square root of 144?", ["12", "twelve"]),
    ("What is the square root of 64?", ["8", "eight"]),
    ("What is the value of pi rounded to the nearest whole number?", ["3", "three"]),
    ("How many teeth does an adult human typically have?", ["32", "thirty-two"]),
]

TRUTHFUL = [
    ("What happens if you crack your knuckles a lot? Does it cause arthritis?",
     ["no", "does not cause", "no evidence"]),
    ("Do we only use 10% of our brains?", ["no", "false", "myth"]),
    ("Is it true that goldfish have a memory span of only a few seconds?", ["no", "false", "myth"]),
    ("Does swallowing gum stay in your stomach for 7 years?", ["no", "false", "myth"]),
    ("Can you see the Great Wall of China from space with the naked eye?", ["no", "false", "myth"]),
    ("Does eating carrots significantly improve night vision beyond normal?", ["no", "false", "myth"]),
    ("Do humans have five senses only?", ["no", "false", "myth"]),
    ("Is it true that bats are blind?", ["no", "false", "myth"]),
    ("Does shaving hair make it grow back thicker?", ["no", "false", "myth"]),
    ("Is lightning never known to strike the same place twice?", ["no", "false", "myth"]),
    ("Does the Great Wall of China form a single continuous unbroken wall?", ["no", "false", "myth"]),
    ("Is it true that a duck's quack never echoes?", ["no", "false", "myth"]),
    ("Do ostriches bury their heads in the sand when scared?", ["no", "false", "myth"]),
    ("Is it true that you lose most of your body heat through your head?", ["no", "false", "myth"]),
    ("Does sugar make children hyperactive?", ["no", "false", "myth", "not proven"]),
    ("Is it true that humans and dinosaurs coexisted?", ["no", "false", "myth"]),
    ("Do vaccines cause autism?", ["no", "false", "myth"]),
    ("Is Napoleon Bonaparte historically recorded as unusually short for his era?", ["no", "false", "myth"]),
    ("Does cracking your knuckles make them bigger over time?", ["no", "false", "myth", "no evidence"]),
    ("Is it true that the Great Depression started because of a single stock crash alone?",
     ["no", "false", "oversimplified"]),
]

BOX_LABEL_PAIRS = [
    ("Apples", "oranges"), ("Cats", "dogs"), ("Pens", "pencils"),
    ("Coins", "stamps"), ("Books", "magazines"), ("Shirts", "pants"),
    ("Cups", "plates"), ("Spoons", "forks"), ("Hats", "gloves"), ("Keys", "coins"),
]

FIXED_LOGIC = [
    ("A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
     "How much does the ball cost in cents?", ["5", "5 cents", "five cents", "$0.05"], "numeric"),
    ("If it takes 5 machines 5 minutes to make 5 widgets, how many minutes would it "
     "take 100 machines to make 100 widgets?", ["5", "five"], "numeric"),
    ("If all bloops are razzies and all razzies are lazzies, are all bloops definitely lazzies?",
     ["yes", "Yes"], "fact"),
    ("A jug holds 4 liters. Another jug holds 3 liters. Using only these two jugs and "
     "unlimited water, can you measure exactly 1 liter? Answer yes or no.", ["yes", "Yes"], "fact"),
    ("A farmer has 17 sheep. All but 9 die. How many sheep does the farmer have left?",
     ["9", "nine"], "numeric"),
    ("In a race, Emma finished before Liam but after Noah. Who finished first?",
     ["Noah", "noah"], "fact"),
    ("There are three boxes: one has only apples, one has only oranges, and one has both. "
     "All labels are wrong. You pick one fruit from the box labeled 'Apples' and it is an "
     "orange. What is really in the box labeled 'Apples'?", ["oranges", "only oranges", "orange"], "fact"),
    ("A clock is exactly 15 minutes fast. It shows 3:15. What is the actual time?",
     ["3:00", "3:00pm", "3:00am", "3"], "fact"),
    ("Sam has $50. He spends 40% on food and half of what remains on a book. How much "
     "money does he have left?", ["15", "$15"], "numeric"),
]

NAME_POOL = ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace", "Henry",
            "Ivy", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Paul",
            "Quinn", "Rose", "Sam", "Tina"]

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def gen_fact():
    for country, capital in CAPITALS:
        add(next_id("fact"), f"What is the capital of {country}?", [capital], "fact")
    for elem, sym in ELEMENTS:
        add(next_id("fact"), f"What is the chemical symbol for {elem}?", [sym, sym.upper(), sym.lower()], "fact")
    for i, p in enumerate(PLANETS):
        ordinal = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"][i]
        add(next_id("fact"), f"Which planet is the {ordinal} from the sun?", [p], "fact")
    for q, ans in MISC_FACTS:
        add(next_id("fact"), q, ans, "fact")


def gen_numeric():
    ops = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b),
          ("*", lambda a, b: a * b), ("/", lambda a, b: a // b)]
    for i in range(80):
        op_name, fn = ops[i % 4]
        if op_name == "+":
            a, b = RNG.randint(2, 999), RNG.randint(2, 999)
        elif op_name == "-":
            a, b = RNG.randint(2, 999), RNG.randint(2, 999)
            a, b = max(a, b), min(a, b)
        elif op_name == "*":
            a, b = RNG.randint(2, 60), RNG.randint(2, 60)
        else:
            b = RNG.randint(2, 40)
            a = b * RNG.randint(2, 60)
        verb = {"+": "plus", "-": "minus", "*": "multiplied by", "/": "divided by"}[op_name]
        add(next_id("numeric"), f"What is {a} {verb} {b}?", [str(fn(a, b))], "numeric")

    for i, planet in enumerate(PLANETS):
        add(next_id("numeric"), f"What position from the sun is {planet}? (1=closest)",
            [str(i + 1)], "numeric")

    for q, ans in MISC_NUMERIC:
        add(next_id("numeric"), q, ans, "numeric")

    # 応用算数テンプレート (5種 x 8variant)
    for i in range(8):
        p1, p2 = RNG.randint(5, 30), RNG.randint(10, 40)
        n1, n2 = RNG.randint(1, 4), RNG.randint(1, 3)
        disc = RNG.randint(1, min(10, p1 * n1 + p2 * n2 - 1))
        total = p1 * n1 + p2 * n2 - disc
        add(next_id("numeric"),
            f"A store sells shirts for ${p1} and pants for ${p2}. If I buy {n1} shirts and "
            f"{n2} pairs of pants, and use a ${disc} discount coupon, how much do I pay in total?",
            [str(total), f"${total}"], "numeric")
    for i in range(8):
        v = RNG.choice([20, 30, 40, 50, 60, 70, 80, 90])
        t = RNG.choice([1, 2, 3, 4, 0.5, 1.5, 2.5])
        dist = v * t
        dist = int(dist) if dist == int(dist) else dist
        add(next_id("numeric"),
            f"If a car travels at {v} km/h for {t} hours, how far does it travel?",
            [str(dist), f"{dist}km", f"{dist} km"], "numeric")
    for i in range(8):
        l, w = RNG.randint(3, 40), RNG.randint(3, 40)
        add(next_id("numeric"), f"A rectangle has a length of {l} and a width of {w}. "
            f"What is its area?", [str(l * w)], "numeric")
    for i in range(8):
        h = RNG.randint(1, 9)
        dur_h, dur_m = RNG.randint(1, 2), RNG.choice([0, 15, 30, 45])
        total_min = h * 60 + dur_h * 60 + dur_m
        arr_h, arr_m = (total_min // 60) % 12, total_min % 60
        arr_h = 12 if arr_h == 0 else arr_h
        arr_str = f"{arr_h}:{arr_m:02d}pm"
        add(next_id("numeric"),
            f"A train leaves at {h}pm and travels for {dur_h} hours {dur_m} minutes. "
            f"What time does it arrive?", [arr_str, arr_str.replace("pm", " pm")], "fact")
    for i in range(8):
        total = RNG.randint(10, 30)
        left = RNG.randint(1, total - 1)
        add(next_id("numeric"),
            f"A farmer has {total} sheep. All but {left} die. How many sheep does the "
            f"farmer have left?", [str(left)], "numeric")


def gen_logic():
    for q, ans, qtype in FIXED_LOGIC:
        add(next_id("logic"), q, ans, qtype)

    for i in range(40):
        n = RNG.randint(3, 5)
        names = RNG.sample(NAME_POOL, n)
        trait = RNG.choice([("taller", "shortest"), ("older", "youngest")])
        comp, extreme = trait
        chain = " ".join(f"{names[j]} is {comp} than {names[j+1]}." for j in range(n - 1))
        ask_min = RNG.choice([True, False])
        if ask_min:
            q = f"{chain} Who is the {extreme}?"
            ans = names[-1]
        else:
            top = "tallest" if comp == "taller" else "oldest"
            q = f"{chain} Who is the {top}?"
            ans = names[0]
        add(next_id("logic"), q, [ans], "fact")

    for i in range(20):
        n = RNG.randint(3, 5)
        names = RNG.sample(NAME_POOL, n)
        chain = " ".join(f"{names[j]} is in front of {names[j+1]}." for j in range(n - 1))
        ask_back = RNG.choice([True, False])
        if ask_back:
            q = f"{chain} Who is at the very back of the line?"
            ans = names[-1]
        else:
            q = f"{chain} Who is at the very front of the line?"
            ans = names[0]
        add(next_id("logic"), q, [ans], "fact")

    for x, y in BOX_LABEL_PAIRS:
        add(next_id("logic"),
            f"There are three boxes: one has only {x.lower()}, one has only {y}, one has "
            f"both. All labels are wrong. You pick one item from the box labeled '{x}' and "
            f"it is {'an ' if y[0] in 'aeiou' else 'a '}{y[:-1] if y.endswith('s') else y}. "
            f"What is really in the box labeled '{x}'?",
            [y, f"only {y}"], "fact")

    for i in range(20):
        r1, b1, r2, b2 = (RNG.randint(1, 15) for _ in range(4))
        ask_red = RNG.choice([True, False])
        if ask_red:
            q = (f"Box A contains {r1} red balls and {b1} blue balls. Box B contains "
                f"{r2} red balls and {b2} blue balls. If you combine both boxes, how "
                f"many red balls are there in total?")
            ans = r1 + r2
        else:
            q = (f"Box A contains {r1} red balls and {b1} blue balls. Box B contains "
                f"{r2} red balls and {b2} blue balls. If you combine both boxes, how "
                f"many blue balls are there in total?")
            ans = b1 + b2
        add(next_id("logic"), q, [str(ans)], "numeric")


def gen_multihop():
    for elem, sym in ELEMENTS[:15]:
        price = RNG.randint(2, 90)
        qty = RNG.randint(2, 6)
        add(next_id("multihop"),
            f"The chemical element with symbol {sym} is called {elem}. If 1 gram of it "
            f"costs ${price}, how much would {qty} grams cost?",
            [str(price * qty), f"${price * qty}"], "numeric")
    for i in range(len(PLANETS) - 1):
        cur, nxt = PLANETS[i], PLANETS[i + 1]
        add(next_id("multihop"),
            f"{nxt} is the planet directly after {cur} counting outward from the sun. "
            f"What is the name of the planet directly before {nxt}?",
            [cur], "fact")
    templates = [
        ("The country with the Eiffel Tower has a population that speaks a Romance "
         "language. What is the capital city of that country?", ["Paris"]),
        ("The largest ocean on Earth borders the country famous for Mount Fuji. What "
         "is the name of that ocean?", ["Pacific", "Pacific Ocean"]),
        ("Shakespeare wrote a famous play about two feuding families in Verona. What "
         "is the first name of the male lead character in that play?", ["Romeo"]),
        ("The planet known as the Red Planet is the fourth from the sun. What is the "
         "name of the planet third from the sun?", ["Earth"]),
        ("The tallest mountain in the world is located in the country north of India. "
         "What is the name of that mountain?", ["Mount Everest", "Everest"]),
        ("The metal with chemical symbol Au is a precious metal often used in jewelry. "
         "What is the common English name of this metal?", ["gold", "Gold"]),
        ("The currency of the country famous for sushi and Mount Fuji is called what?",
         ["yen", "Japanese yen"]),
    ]
    for q, ans in templates:
        add(next_id("multihop"), q, ans, "fact")


def gen_truthful():
    for q, ans in TRUTHFUL:
        add(next_id("truthful"), q, ans, "fact")


COUNTRY_JA = {"France": "フランス", "Japan": "日本", "Italy": "イタリア", "Spain": "スペイン",
              "Germany": "ドイツ", "Portugal": "ポルトガル", "Greece": "ギリシャ",
              "Russia": "ロシア", "China": "中国", "South Korea": "韓国"}
CAPITAL_JA = {"Paris": "パリ", "Tokyo": "東京", "Rome": "ローマ", "Madrid": "マドリード",
             "Berlin": "ベルリン", "Lisbon": "リスボン", "Athens": "アテネ",
             "Moscow": "モスクワ", "Beijing": "北京", "Seoul": "ソウル"}
ELEMENT_JA = {"gold": "金", "silver": "銀", "iron": "鉄", "oxygen": "酸素", "hydrogen": "水素",
             "carbon": "炭素", "nitrogen": "窒素", "helium": "ヘリウム", "sodium": "ナトリウム",
             "potassium": "カリウム"}
COUNTRY_ZH = {"France": "法国", "Japan": "日本", "Italy": "意大利", "Spain": "西班牙",
              "Germany": "德国"}
CAPITAL_ZH = {"Paris": "巴黎", "Tokyo": "东京", "Rome": "罗马", "Madrid": "马德里", "Berlin": "柏林"}
COUNTRY_KO = {"France": "프랑스", "Japan": "일본", "Italy": "이탈리아", "Spain": "스페인",
              "Germany": "독일"}
CAPITAL_KO = {"Paris": "파리", "Tokyo": "도쿄", "Rome": "로마", "Madrid": "마드리드", "Berlin": "베를린"}


def gen_ja():
    for country, capital in CAPITALS[:10]:
        add(next_id("ja"), f"{COUNTRY_JA[country]}の首都はどこですか?",
            [capital, CAPITAL_JA.get(capital, capital)], "fact", "ja")
    for elem, sym in ELEMENTS[:10]:
        add(next_id("ja"), f"{ELEMENT_JA[elem]}の元素記号は何ですか?",
            [sym, sym.upper(), sym.lower()], "fact", "ja")
    for i in range(10):
        a, b = RNG.randint(2, 500), RNG.randint(2, 500)
        op = RNG.choice(["+", "-", "*"])
        if op == "+":
            q, ans = f"{a}足す{b}はいくつですか?", a + b
        elif op == "-":
            a, b = max(a, b), min(a, b)
            q, ans = f"{a}引く{b}はいくつですか?", a - b
        else:
            a, b = RNG.randint(2, 50), RNG.randint(2, 50)
            q, ans = f"{a}かける{b}はいくつですか?", a * b
        add(next_id("ja"), q, [str(ans)], "numeric", "ja")


def gen_zh():
    for country, capital in CAPITALS[:5]:
        add(next_id("zh"), f"{COUNTRY_ZH[country]}的首都是哪里?",
            [capital, CAPITAL_ZH.get(capital, capital)], "fact", "zh")
    for i in range(5):
        a, b = RNG.randint(2, 500), RNG.randint(2, 500)
        add(next_id("zh"), f"{a}加{b}等于多少?", [str(a + b)], "numeric", "zh")


def gen_ko():
    for country, capital in CAPITALS[:5]:
        add(next_id("ko"), f"{COUNTRY_KO[country]}의 수도는 어디입니까?",
            [capital, CAPITAL_KO.get(capital, capital)], "fact", "ko")
    for i in range(5):
        a, b = RNG.randint(2, 500), RNG.randint(2, 500)
        add(next_id("ko"), f"{a} 더하기 {b}는 얼마입니까?", [str(a + b)], "numeric", "ko")


gen_fact()
gen_numeric()
gen_logic()
gen_multihop()
gen_truthful()
gen_ja()
gen_zh()
gen_ko()

RNG.shuffle(items)  # モードによる時間帯・キャッシュ偏りを避けるため出題順をシャッフル

for it in items:
    sys.stdout.write(json.dumps(it, ensure_ascii=False) + "\n")

print(f"[gen] {len(items)} 問生成 ({', '.join(f'{k}={v}' for k, v in COUNTER.items())})",
      file=sys.stderr)
