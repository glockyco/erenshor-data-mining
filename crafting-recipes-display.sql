-- Crafting Recipes Display: Molds with their outputs and inputs
-- Shows recipe item, what it produces, and required materials

WITH RecipeOutputs AS (
    SELECT
        recipe_item.Id as RecipeItemId,
        recipe_item.ItemName as RecipeName,
        GROUP_CONCAT(output_item.ItemName, ', ') as Outputs
    FROM CraftingRewards rw
    JOIN Items recipe_item ON rw.RecipeItemId = recipe_item.Id
    JOIN Items output_item ON rw.RewardItemId = output_item.Id
    GROUP BY recipe_item.Id, recipe_item.ItemName
),
RecipeInputs AS (
    SELECT
        r.RecipeItemId,
        GROUP_CONCAT(input_item.ItemName, ', ') as Inputs
    FROM CraftingRecipes r
    JOIN Items input_item ON r.MaterialItemId = input_item.Id
    GROUP BY r.RecipeItemId
)
SELECT
    ro.RecipeName as 'Recipe Item',
    ro.Outputs as 'Outputs',
    COALESCE(ri.Inputs, 'None') as 'Inputs'
FROM RecipeOutputs ro
LEFT JOIN RecipeInputs ri ON ro.RecipeItemId = ri.RecipeItemId
ORDER BY ro.RecipeName;
