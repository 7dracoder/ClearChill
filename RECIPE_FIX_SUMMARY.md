# Recipe Section Fix - Single Item Support

## Problem
The recipe section wasn't showing recipes when the fridge had only a single item. Users expected to see recipe suggestions even with minimal inventory.

## Root Cause
1. **Existing recipes required multiple ingredients** - All 5 seeded recipes needed 3-4 ingredients
2. **No simple single-ingredient recipes** - Database lacked recipes that could be made with just one item
3. **Urgency scoring system** - Recipes were sorted by urgency score (based on expiring ingredients), but all recipes were still shown

## Solution

### 1. Added Simple Single-Ingredient Recipes
Added 5 new simple recipes that work with minimal ingredients:
- **Simple Scrambled Eggs** - Just eggs + butter (both pantry staples)
- **Sautéed Spinach** - Just spinach + olive oil
- **Roasted Chicken Breast** - Just chicken + olive oil
- **Steamed Broccoli** - Just broccoli (single ingredient!)
- **Pan-Seared Salmon** - Just salmon + olive oil

### 2. Fixed Supabase Environment Variables
Fixed incorrect environment variable names in `supabase_client.py`:
- Changed `SUPABASE_SERVICE_KEY` → `SUPABASE_SERVICE_ROLE_KEY`
- Changed `SUPABASE_KEY` → `SUPABASE_ANON_KEY`

### 3. Updated Seed Data
Modified `seed_recipes.py` to include the new simple recipes at the beginning of the list, ensuring they're prioritized for users with minimal inventory.

### 4. Improved Empty State Message
Updated frontend message from "Add more items to your fridge" to "Try adjusting your filters or add items to your fridge" for better UX.

## Files Changed
- `fridge_observer/seed_recipes.py` - Added 5 simple recipes
- `fridge_observer/supabase_client.py` - Fixed environment variable names
- `static/js/recipes.js` - Improved empty state message
- `add_simple_recipes.py` - Migration script to add recipes to existing database

## How It Works Now
1. Users with a single item (e.g., just spinach) will see "Sautéed Spinach" recipe
2. Users with just chicken will see "Roasted Chicken Breast"
3. Users with just broccoli will see "Steamed Broccoli"
4. Recipes are sorted by urgency score (expiring ingredients first)
5. All recipes are shown regardless of score - no filtering

## Testing
Run the migration script to add recipes to your Supabase database:
```bash
python add_simple_recipes.py
```

The script checks for existing recipes and only adds new ones, so it's safe to run multiple times.

## Deployment
The changes have been pushed to GitHub. On Render:
1. The deployment will automatically pick up the new code
2. The `seed_recipes()` function runs on startup
3. New recipes will be available immediately
4. Existing recipes are preserved

## Future Improvements
- Add more single-ingredient recipes for common items
- Consider adding "pantry staple" recipes that assume basic ingredients
- Add recipe difficulty levels (beginner, intermediate, advanced)
- Allow users to mark ingredients they always have on hand
