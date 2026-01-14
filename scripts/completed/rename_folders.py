"""Rename folders 1-30 (truncated + colon/format fixes)"""
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

va_path = Path(r"/path/to/music/Various Artists")

# Define renames: (old_name, new_name)
renames = [
    # Category 1: Truncated Names (1-19)
    ("Bossa Tres Jazz II - Step Into The Galle", "Bossa Tres Jazz II - Step Into The Gallery"),
    ("Def Jam Music Group Inc. - 10th Year Anni", "Def Jam Music Group Inc. - 10th Year Anniversary"),
    ("Fame Club (Premium House & Electro Tunes", "Fame Club (Premium House & Electro Tunes)"),
    ("Flamenco - A Windham Hill Guitar Collecti", "Flamenco - A Windham Hill Guitar Collection"),
    ("Lounge Classics Double Pack- 40 Timeless", "Lounge Classics Double Pack- 40 Timeless Chilled Cool Bar Grooves"),
    ("Mass - The Most Powerful, Uplifting & Pas", "Mass - The Most Powerful, Uplifting & Passionate Music You Will Ever Hear"),
    ("Ministry of Sound - The Annual 2003 [Aust", "Ministry of Sound - The Annual 2003 [Australia]"),
    ("Putumayo Presents - A Mediterranean Odyss", "Putumayo Presents - A Mediterranean Odyssey"),
    ("Putumayo Presents - Music from the Chocol", "Putumayo Presents - Music from the Chocolate Lands"),
    ("Putumayo Presents - Music from the Tea La", "Putumayo Presents - Music from the Tea Lands"),
    ("Putumayo Presents - Music from the Wine L", "Putumayo Presents - Music from the Wine Lands"),
    ("Putumayo Presents - Salsa Around the Worl", "Putumayo Presents - Salsa Around the World"),
    ("Putumayo Presents - Women of Latin Americ", "Putumayo Presents - Women of Latin America"),
    ("Riesling Lounge - Smooth Vibes for a Love", "Riesling Lounge - Smooth Vibes for a Lovely Atmosphere"),
    ("Sweet Dreams - Baby's First Classics, Vol", "Sweet Dreams - Baby's First Classics, Vol. 2"),
    ("The Best of Sessions at West 54th, Vol_", "The Best of Sessions at West 54th, Vol. 1"),
    ("The Chemistry Set (The Ultimate Compilat", "The Chemistry Set (The Ultimate Compilation Of Slammin' Big Beats)"),
    ("The Source Presents - Hip Hop Hits, Vol_", "The Source Presents - Hip Hop Hits, Vol. 7"),
    ("Thrivemix, Vol. 3 - Mixed by DJ Skribble", "Thrivemix, Vol. 3 - Mixed by DJ Skribble and Vic Latino"),

    # Category 2: Colon/Format Fixes (20-30)
    ("Asia Lounge - Asian Flavoured Club Tunes", "Asia Lounge - Asian Flavoured Club Tunes - 3rd Floor"),
    ("Café Buddha - The Cream of Lounge Cuisine", "Cafe Buddha - The Cream of Lounge Cuisine"),
    ("Café de Flore - Rendez-vous à Saint-Germain-des-Prés", "Café de Flore - Rendez-Vous a Saint Germain des Pres [Sunnyside]"),
    ("Lullaby a collection", "Lullaby - A Collection"),
    ("Monsieur Gainsbourg Revisited", "Monsieur Gainsbourg - Revisited"),
    ("Putumayo Presents - French Café", "Putumayo Presents - French Cafe"),
    ("Putumayo Presents - ¡Baila! A Latin Dance Party", "Putumayo Presents - Baila- A Latin Dance Party"),
    ("Radio 1's Live Lounge, Volume 4", "Radio 1's Live Lounge - Volume 4"),
    ("Radio 1's Live Lounge, Volume 5", "Radio 1's Live Lounge - Volume 5"),
    ("Shine_ The Complete Classics", "Shine - The Complete Classics"),
    ("The Chillout Session - Summer Collection 2003", "The Chillout Session - Summer Collection [2003]"),
]

print(f"Renaming {len(renames)} folders...")
print()

success = 0
failed = 0

for i, (old_name, new_name) in enumerate(renames, 1):
    old_path = va_path / old_name
    new_path = va_path / new_name

    if old_path.exists():
        try:
            old_path.rename(new_path)
            print(f"{i:2}. OK: {old_name}")
            print(f"      → {new_name}")
            success += 1
        except Exception as e:
            print(f"{i:2}. FAILED: {old_name}")
            print(f"      Error: {e}")
            failed += 1
    else:
        print(f"{i:2}. SKIP: {old_name} (not found)")

print()
print(f"Done: {success} renamed, {failed} failed")
