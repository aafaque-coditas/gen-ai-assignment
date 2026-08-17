"""
10 word problems used by math_solver.py's --test mode, each with a known
correct numeric answer to check chain-of-thought extraction against.
"""

MATH_PROBLEMS = [
    (
        "Roger has 5 tennis balls. He buys 2 more cans of tennis balls. "
        "Each can has 3 tennis balls. How many tennis balls does he have now?",
        11,
    ),
    (
        "A bakery sells cupcakes for $3 each. Maria buys 4 cupcakes and pays "
        "with a $20 bill. How much change does she get, in dollars?",
        8,
    ),
    (
        "There are 24 students in a class. If 3/8 of them are boys, how many "
        "girls are in the class?",
        15,
    ),
    (
        "A train travels at 60 miles per hour. How far does it travel in 2.5 "
        "hours, in miles?",
        150,
    ),
    (
        "Sarah has $45. She spends $12 on a book and $8 on lunch. How much "
        "money does she have left, in dollars?",
        25,
    ),
    (
        "A rectangular garden is 8 meters long and 5 meters wide. What is its "
        "area in square meters?",
        40,
    ),
    (
        "A recipe calls for 2 cups of flour to make 12 cookies. How many cups "
        "of flour are needed to make 30 cookies?",
        5,
    ),
    (
        "Tom is saving for a $150 bike. He has saved $45 already and earns $15 "
        "per week from his job. How many whole weeks until he can afford the bike?",
        7,
    ),
    (
        "A store had 100 items in stock. It sold 35% of them on Monday, then "
        "sold 20% of the remaining items on Tuesday. How many items are left "
        "after Tuesday?",
        52,
    ),
    (
        "Three friends split a $90 restaurant bill equally, then add a 10% tip "
        "on the original bill, split evenly among them. How much does each "
        "friend pay in total, in dollars?",
        33,
    ),
]
