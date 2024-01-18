import os, re, pandas as pd, numpy as np
from tqdm.auto import tqdm
import py_stringmatching as sm


def get_edh_deck(commander):
    file = open(f"decks/{commander}.txt","r+")
    deck = pd.Series(file.readlines(), name = "Name").str.replace("\\n", "", regex = True)
    file.close()
    deck = deck.rename("Name").to_frame()
    deck = deck.assign(Quantity = deck.Name.str.split(" ").apply(lambda l : l[0]).astype(int), Group = commander)
    deck["Name"] = deck["Name"].str.split(" ").apply(lambda l : " ".join(l[1:])).str.replace("\s\(.{3,5}\).*", "", regex = True)
    
    lands = get_lands("decks/LandPack.txt")
    deck["is_land"] = deck["Name"].isin(lands)
    return deck

def get_cube(file_name):
    cube = pd.read_csv(file_name, usecols = ["Name", "Type"])
    cube = cube.assign(is_land = cube.Type.str.contains("Land"))[["Name", "is_land"]]
    cube = cube.groupby(cube.columns.tolist(),as_index=False).size().rename(columns = {"size" : "Quantity"})
    return cube

def get_lands(file_name):
    with open(file_name,"r+") as file:
        lands = pd.Series(file.readlines(), name = "Name").str.replace("\\n", "", regex = True).replace("", np.nan, regex = True).dropna()
    return lands

def get_final_order(decks):
    decks = decks.loc[~decks.Name.isin(["Mountain", "Island", "Forest", "Swamp", "Plains", " Forest", " Plains", " Swamp", " Island"])]


    #Cap all non-cube card to 4 exemplaries
    decks = decks.assign(is_cube = decks["Group"].eq("Cube"))
    is_cube_quantity = decks.groupby(["is_cube", "Name"]).Quantity.sum()
    is_cube_quantity.update(is_cube_quantity.xs(False, level= 0, drop_level = False).map(lambda qt : min(qt, 4)))
    final_cards = pd.pivot_table(is_cube_quantity.to_frame(), values = "Quantity", columns = "is_cube", index = "Name", aggfunc = "sum")\
        .fillna(0).astype(int).sum(axis = 1).clip(upper = 4)

    #Add basic lands
    basics = pd.DataFrame({"Quantity" : [20]*5, "Name" : ["Mountain", "Island", "Forest", "Swamp", "Plains"]})#decks.loc[decks.Name.isin(["Mountain", "Island", "Forest", "Swamp", "Plains"])]
    final_cards = pd.concat([basics.set_index("Name").squeeze(), final_cards]).rename("Quantity")

    #Add custom cards
    custom_cards = pd.Series(["Ichormoon Gauntlet", "The Eternal Wanderer"], name = "Name")
    custom_cards = pd.Series([1, 1], index = custom_cards)
    final_cards = pd.concat([final_cards, pd.Series(custom_cards)]).rename("Quantity")
    
    return final_cards

def create_card_table(commanders, cube_dir):
    #Concatenate all commanders
    cube = get_cube(cube_dir)
    cube["Group"] = "Cube"
    
    decks = cube.copy()
    for commander in tqdm(commanders):
        deck = get_edh_deck(commander)
        decks = pd.concat([decks, deck]).reset_index(drop = True)


    #Create final order from decklists
    final_cards = get_final_order(decks)

    #Deduce cards that are shared
    deck_quantities = decks.groupby("Name").Quantity.sum().rename("Decks")
    comp = pd.concat([deck_quantities, final_cards.rename("Ordered")], axis = 1).fillna(0).astype(int)
    comp = comp.diff(axis = 1).iloc[:, -1]
    cards_to_share = comp.loc[comp.lt(0)].index

    #Add tag to these cards
    additional_shared_cards = ["Mountain", "Island", "Forest", "Swamp", "Plains"] #Basic lands and some cards that I forgot to print
    decks = decks.assign(is_shared = decks.Name.isin(list(cards_to_share) + additional_shared_cards))
    
    return decks[["Name", "Group", "Quantity", "is_shared", "is_land"]]

def get_subset(decks, group = None, is_shared = None, is_land = None):
    group_mask = True if group is None else decks.Group.eq(group)
    is_shared_mask = True if is_shared is None else decks.is_shared.eq(is_shared)
    is_land_mask = True if is_land is None else decks.is_land.eq(is_land)
    return decks.loc[group_mask & is_shared_mask & is_land_mask].sort_values(by = ["is_shared", "is_land"])