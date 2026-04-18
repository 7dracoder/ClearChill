"""Seed sample recipes into the database on first startup."""
import json
from fridge_observer.db import get_db

SAMPLE_RECIPES = [
    {
        "name": "Spinach & Mushroom Omelette",
        "description": "A quick and nutritious breakfast omelette packed with vegetables.",
        "cuisine": "French",
        "dietary_tags": ["vegetarian", "gluten-free"],
        "prep_minutes": 10,
        "instructions": "1. Whisk 3 eggs. 2. Sauté mushrooms and spinach in butter. 3. Pour eggs over vegetables. 4. Fold and serve.",
        "image_url": None,
        "ingredients": [
            {"name": "eggs", "category": "dairy", "is_pantry_staple": 1},
            {"name": "spinach", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "mushrooms", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "butter", "category": "dairy", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Chicken Stir-Fry",
        "description": "A vibrant Asian-inspired stir-fry with colorful vegetables.",
        "cuisine": "Asian",
        "dietary_tags": ["gluten-free"],
        "prep_minutes": 20,
        "instructions": "1. Slice chicken breast. 2. Stir-fry with bell peppers, broccoli, and carrots. 3. Add soy sauce and sesame oil. 4. Serve over rice.",
        "image_url": None,
        "ingredients": [
            {"name": "chicken breast", "category": "meat", "is_pantry_staple": 0},
            {"name": "bell peppers", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "broccoli", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "carrots", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "soy sauce", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "rice", "category": "packaged_goods", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Caprese Salad",
        "description": "Classic Italian salad with fresh tomatoes, mozzarella, and basil.",
        "cuisine": "Italian",
        "dietary_tags": ["vegetarian", "gluten-free"],
        "prep_minutes": 5,
        "instructions": "1. Slice tomatoes and mozzarella. 2. Arrange alternately on a plate. 3. Add fresh basil leaves. 4. Drizzle with olive oil and balsamic vinegar.",
        "image_url": None,
        "ingredients": [
            {"name": "tomatoes", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "mozzarella", "category": "dairy", "is_pantry_staple": 0},
            {"name": "basil", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "olive oil", "category": "packaged_goods", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Beef Tacos",
        "description": "Juicy ground beef tacos with fresh toppings.",
        "cuisine": "Mexican",
        "dietary_tags": [],
        "prep_minutes": 25,
        "instructions": "1. Brown ground beef with taco seasoning. 2. Warm tortillas. 3. Fill with beef, shredded lettuce, tomato, cheese, and sour cream.",
        "image_url": None,
        "ingredients": [
            {"name": "ground beef", "category": "meat", "is_pantry_staple": 0},
            {"name": "tortillas", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "lettuce", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "tomatoes", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "cheddar cheese", "category": "dairy", "is_pantry_staple": 0},
            {"name": "sour cream", "category": "dairy", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Vegetable Curry",
        "description": "A warming Indian-inspired curry with seasonal vegetables.",
        "cuisine": "Indian",
        "dietary_tags": ["vegetarian", "vegan", "gluten-free"],
        "prep_minutes": 35,
        "instructions": "1. Sauté onion and garlic. 2. Add curry paste and coconut milk. 3. Add diced vegetables. 4. Simmer 20 minutes. 5. Serve with rice.",
        "image_url": None,
        "ingredients": [
            {"name": "potatoes", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "cauliflower", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "spinach", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "coconut milk", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "curry paste", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "onion", "category": "vegetables", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Greek Yogurt Parfait",
        "description": "A refreshing layered parfait with berries and granola.",
        "cuisine": "Mediterranean",
        "dietary_tags": ["vegetarian", "gluten-free"],
        "prep_minutes": 5,
        "instructions": "1. Layer Greek yogurt in a glass. 2. Add mixed berries. 3. Top with granola and honey.",
        "image_url": None,
        "ingredients": [
            {"name": "Greek yogurt", "category": "dairy", "is_pantry_staple": 0},
            {"name": "strawberries", "category": "fruits", "is_pantry_staple": 0},
            {"name": "blueberries", "category": "fruits", "is_pantry_staple": 0},
            {"name": "granola", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "honey", "category": "packaged_goods", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Pasta Primavera",
        "description": "Light and fresh pasta with spring vegetables.",
        "cuisine": "Italian",
        "dietary_tags": ["vegetarian"],
        "prep_minutes": 25,
        "instructions": "1. Cook pasta al dente. 2. Sauté zucchini, cherry tomatoes, and asparagus. 3. Toss with pasta, olive oil, and Parmesan.",
        "image_url": None,
        "ingredients": [
            {"name": "pasta", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "zucchini", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "cherry tomatoes", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "asparagus", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "Parmesan", "category": "dairy", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Salmon with Lemon Butter",
        "description": "Pan-seared salmon with a bright lemon butter sauce.",
        "cuisine": "French",
        "dietary_tags": ["gluten-free"],
        "prep_minutes": 15,
        "instructions": "1. Season salmon fillets. 2. Pan-sear 4 minutes per side. 3. Make lemon butter sauce. 4. Serve with steamed vegetables.",
        "image_url": None,
        "ingredients": [
            {"name": "salmon", "category": "meat", "is_pantry_staple": 0},
            {"name": "lemon", "category": "fruits", "is_pantry_staple": 0},
            {"name": "butter", "category": "dairy", "is_pantry_staple": 1},
            {"name": "green beans", "category": "vegetables", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Avocado Toast",
        "description": "Creamy avocado on toasted sourdough with toppings.",
        "cuisine": "Modern",
        "dietary_tags": ["vegetarian", "vegan"],
        "prep_minutes": 5,
        "instructions": "1. Toast sourdough bread. 2. Mash avocado with lemon juice and salt. 3. Spread on toast. 4. Top with cherry tomatoes and red pepper flakes.",
        "image_url": None,
        "ingredients": [
            {"name": "avocado", "category": "fruits", "is_pantry_staple": 0},
            {"name": "sourdough bread", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "cherry tomatoes", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "lemon", "category": "fruits", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Mango Smoothie",
        "description": "A tropical smoothie with mango, banana, and yogurt.",
        "cuisine": "Tropical",
        "dietary_tags": ["vegetarian", "gluten-free"],
        "prep_minutes": 5,
        "instructions": "1. Blend mango chunks, banana, Greek yogurt, and orange juice. 2. Pour into glasses and serve immediately.",
        "image_url": None,
        "ingredients": [
            {"name": "mango", "category": "fruits", "is_pantry_staple": 0},
            {"name": "banana", "category": "fruits", "is_pantry_staple": 0},
            {"name": "Greek yogurt", "category": "dairy", "is_pantry_staple": 0},
            {"name": "orange juice", "category": "beverages", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Cheese Quesadillas",
        "description": "Crispy quesadillas with melted cheese and salsa.",
        "cuisine": "Mexican",
        "dietary_tags": ["vegetarian"],
        "prep_minutes": 10,
        "instructions": "1. Place tortilla in pan. 2. Add shredded cheese and fold. 3. Cook until golden on both sides. 4. Serve with salsa and sour cream.",
        "image_url": None,
        "ingredients": [
            {"name": "flour tortillas", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "cheddar cheese", "category": "dairy", "is_pantry_staple": 0},
            {"name": "sour cream", "category": "dairy", "is_pantry_staple": 0},
            {"name": "bell peppers", "category": "vegetables", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Tomato Basil Soup",
        "description": "A comforting classic tomato soup with fresh basil.",
        "cuisine": "Italian",
        "dietary_tags": ["vegetarian", "vegan", "gluten-free"],
        "prep_minutes": 30,
        "instructions": "1. Roast tomatoes with garlic. 2. Blend with vegetable broth. 3. Season and add fresh basil. 4. Serve with crusty bread.",
        "image_url": None,
        "ingredients": [
            {"name": "tomatoes", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "basil", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "garlic", "category": "vegetables", "is_pantry_staple": 1},
            {"name": "vegetable broth", "category": "packaged_goods", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Berry Overnight Oats",
        "description": "Creamy overnight oats with mixed berries and chia seeds.",
        "cuisine": "Modern",
        "dietary_tags": ["vegetarian", "vegan"],
        "prep_minutes": 5,
        "instructions": "1. Mix oats, almond milk, chia seeds, and maple syrup. 2. Refrigerate overnight. 3. Top with fresh berries before serving.",
        "image_url": None,
        "ingredients": [
            {"name": "oats", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "strawberries", "category": "fruits", "is_pantry_staple": 0},
            {"name": "blueberries", "category": "fruits", "is_pantry_staple": 0},
            {"name": "almond milk", "category": "beverages", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Pork Fried Rice",
        "description": "Classic Chinese-style fried rice with pork and vegetables.",
        "cuisine": "Asian",
        "dietary_tags": [],
        "prep_minutes": 20,
        "instructions": "1. Cook rice and let cool. 2. Stir-fry pork with garlic and ginger. 3. Add vegetables and rice. 4. Season with soy sauce and sesame oil.",
        "image_url": None,
        "ingredients": [
            {"name": "pork", "category": "meat", "is_pantry_staple": 0},
            {"name": "rice", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "carrots", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "peas", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "eggs", "category": "dairy", "is_pantry_staple": 1},
            {"name": "soy sauce", "category": "packaged_goods", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Watermelon Feta Salad",
        "description": "A refreshing summer salad with watermelon, feta, and mint.",
        "cuisine": "Mediterranean",
        "dietary_tags": ["vegetarian", "gluten-free"],
        "prep_minutes": 10,
        "instructions": "1. Cube watermelon. 2. Crumble feta over watermelon. 3. Add fresh mint leaves. 4. Drizzle with lime juice and olive oil.",
        "image_url": None,
        "ingredients": [
            {"name": "watermelon", "category": "fruits", "is_pantry_staple": 0},
            {"name": "feta cheese", "category": "dairy", "is_pantry_staple": 0},
            {"name": "mint", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "lime", "category": "fruits", "is_pantry_staple": 0},
        ],
    },
    {
        "name": "Mushroom Risotto",
        "description": "Creamy Italian risotto with mixed mushrooms and Parmesan.",
        "cuisine": "Italian",
        "dietary_tags": ["vegetarian", "gluten-free"],
        "prep_minutes": 40,
        "instructions": "1. Sauté shallots and garlic. 2. Toast arborio rice. 3. Add warm broth ladle by ladle, stirring constantly. 4. Fold in mushrooms and Parmesan.",
        "image_url": None,
        "ingredients": [
            {"name": "arborio rice", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "mushrooms", "category": "vegetables", "is_pantry_staple": 0},
            {"name": "Parmesan", "category": "dairy", "is_pantry_staple": 0},
            {"name": "vegetable broth", "category": "packaged_goods", "is_pantry_staple": 1},
            {"name": "butter", "category": "dairy", "is_pantry_staple": 1},
        ],
    },
    {
        "name": "Banana Pancakes",
        "description": "Fluffy pancakes with ripe bananas and maple syrup.",
        "cuisine": "American",
        "dietary_tags": ["vegetarian"],
        "prep_minutes": 15,
        "instructions": "1. Mash ripe bananas. 2. Mix with eggs, flour, and milk. 3. Cook on griddle until golden. 4. Serve with maple syrup.",
        "image_url": None,
        "ingredients": [
            {"name": "banana", "category": "fruits", "is_pantry_staple": 0},
            {"name": "eggs", "category": "dairy", "is_pantry_staple": 1},
            {"name": "milk", "category": "dairy", "is_pantry_staple": 0},
            {"name": "flour", "category": "packaged_goods", "is_pantry_staple": 1},
        ],
    },
]


async def seed_recipes() -> None:
    """Seed sample recipes if the recipes table is empty."""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM recipes")
        row = await cursor.fetchone()
        count = row[0] if row else 0

        if count > 0:
            return  # Already seeded

        for recipe_data in SAMPLE_RECIPES:
            ingredients = recipe_data.pop("ingredients")
            dietary_tags = json.dumps(recipe_data["dietary_tags"])

            cursor = await db.execute(
                """INSERT INTO recipes (name, description, cuisine, dietary_tags, prep_minutes, instructions, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    recipe_data["name"],
                    recipe_data["description"],
                    recipe_data["cuisine"],
                    dietary_tags,
                    recipe_data["prep_minutes"],
                    recipe_data["instructions"],
                    recipe_data.get("image_url"),
                ),
            )
            recipe_id = cursor.lastrowid

            for ing in ingredients:
                await db.execute(
                    """INSERT INTO recipe_ingredients (recipe_id, name, category, is_pantry_staple)
                       VALUES (?, ?, ?, ?)""",
                    (recipe_id, ing["name"], ing.get("category"), ing.get("is_pantry_staple", 0)),
                )

            # Restore ingredients for next iteration
            recipe_data["ingredients"] = ingredients

        await db.commit()
