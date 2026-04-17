from load_data import load_recipe_data, load_recipe_save

recipe_data = load_recipe_data()
recipe_save = load_recipe_save()

print(recipe_data.shape)
print(recipe_save.shape)

print(recipe_data.head())
print(recipe_save.head())