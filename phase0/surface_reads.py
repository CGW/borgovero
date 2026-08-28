# -*- coding: utf-8 -*-
"""S003 surface-contamination sample, read in a browser 2026-08-28.

Rule CONFIRMED on 18 listings that publish a breakdown:
    headline Superficie = SUM(surface x coefficient) over rows tagged
    'Principale'.  Verified exactly on 116350107 (1000x100% + 2200x10%
    = 1220), 110972593 (249 + 80x25% + 60x25% = 284) and 115047499
    (80x100% = 80).

'dwelling' below is the sum of RAW residence-type surfaces, i.e. what a
buyer would call the house.
"""
# id, headline, dwelling, note
R = [
 (122343264, 150, 150,  "clean"),
 (122343298, 171, 171,  "clean"),
 (116350107, 1220, 1000, "UP: garden 2200 m2 tagged Principale @10% -> +220"),
 (115047499, 80,  170,  "DOWN: a 90 m2 residence floor tagged Accessoria"),
 (124349853, 84,  84,   "clean"),
 (128374682, 172, 172,  "clean ('other' @100% Principale = the dwelling)"),
 (127626794, 55,  55,   "clean"),
 (110972593, 284, 249,  "UP: two cellars 80+60 tagged Principale @25% -> +35"),
 (122130892, 400, 400,  "clean"),
 (115651313, 350, 350,  "clean"),
 (114468159, 150, 150,  "clean"),
 (43607800,  68,  65,   "UP: cantina 12 m2 tagged Principale @25% -> +3"),
 (126141701, 245, 245,  "clean"),
 (86631746,  120, 120,  "clean"),
 (127104733, 165, 165,  "clean"),
 (130036282, 110, 110,  "clean"),
 (130620684, 100, 100,  "clean"),
 (128457332, 115, 115,  "clean (loft 40 correctly Accessoria @50%)"),
]
NO_BREAKDOWN = [109107031, 80620557]
