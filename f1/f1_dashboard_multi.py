#!/usr/bin/env python3
"""
F1 Season Tracker - Multi-Season Dashboard Generator

Fetched season data is cached in f1_cache.json next to the script.
The generated HTML is fully self-contained — the cache is build-time only.

Usage:
    python3 f1_dashboard_multi.py                        # use cache + baked-in data
    python3 f1_dashboard_multi.py --add 2022 2023 2024 2025  # fetch & cache seasons
    python3 f1_dashboard_multi.py --add 2026             # add 2026 mid-season
    python3 f1_dashboard_multi.py --refresh 2025         # force re-fetch a season
"""

import json, sys, os, time
from datetime import datetime

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "f1_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Keys are strings in JSON, convert back to ints
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"  ⚠️  Cache read error ({e}), starting fresh.")
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in cache.items()}, f, ensure_ascii=False, separators=(',', ':'))
    size_kb = os.path.getsize(CACHE_FILE) / 1024
    print(f"  💾 Cache saved → f1_cache.json ({size_kb:.0f} KB)")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

BASE_URL = "https://api.jolpi.ca/ergast/f1"

FLAG_MAP = {
    "Bahrain":"🇧🇭","Saudi Arabia":"🇸🇦","Australia":"🇦🇺","Japan":"🇯🇵",
    "China":"🇨🇳","USA":"🇺🇸","Italy":"🇮🇹","Monaco":"🇲🇨","Canada":"🇨🇦",
    "Spain":"🇪🇸","Austria":"🇦🇹","UK":"🇬🇧","Great Britain":"🇬🇧",
    "Hungary":"🇭🇺","Belgium":"🇧🇪","Netherlands":"🇳🇱","Azerbaijan":"🇦🇿",
    "Singapore":"🇸🇬","United States":"🇺🇸","Mexico":"🇲🇽","Brazil":"🇧🇷",
    "Qatar":"🇶🇦","Abu Dhabi":"🇦🇪","France":"🇫🇷"
}

TEAM_COLORS = {
    "red_bull":"#3671C6","mclaren":"#FF8000","ferrari":"#E8002D",
    "mercedes":"#27F4D2","aston_martin":"#229971","alpine":"#FF87BC",
    "haas":"#B6BABD","rb":"#6692FF","racing_bulls":"#6692FF",
    "williams":"#64C4FF","kick_sauber":"#52E252","sauber":"#52E252",
    "alfa":"#960000","alphatauri":"#4E7C9B","cadillac":"#C8B4FF",
}

DRIVER_COLORS = [
    "#E8002D","#FF8000","#3671C6","#27F4D2","#229971","#FF87BC",
    "#FFD700","#64C4FF","#B6BABD","#6692FF","#52E252","#FF6B6B",
    "#A78BFA","#34D399","#FCD34D","#F472B6","#60A5FA","#FB923C","#4ADE80","#E879F9"
]

# ─────────────────────────────────────────────────────────────────────────────
# BAKED-IN DATA (standings + race winners only — run --add to get full results)
# ─────────────────────────────────────────────────────────────────────────────

SEASONS_DATA = {

2025: {
    "champion":"Lando Norris","champion_team":"McLaren","ctor_champion":"McLaren",
    "driver_standings":[
        {"position":"1","points":"423","wins":"7","Driver":{"givenName":"Lando","familyName":"Norris","code":"NOR","nationality":"British"},"Constructors":[{"constructorId":"mclaren","name":"McLaren"}]},
        {"position":"2","points":"421","wins":"8","Driver":{"givenName":"Max","familyName":"Verstappen","code":"VER","nationality":"Dutch"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"3","points":"410","wins":"6","Driver":{"givenName":"Oscar","familyName":"Piastri","code":"PIA","nationality":"Australian"},"Constructors":[{"constructorId":"mclaren","name":"McLaren"}]},
        {"position":"4","points":"319","wins":"3","Driver":{"givenName":"George","familyName":"Russell","code":"RUS","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"5","points":"242","wins":"0","Driver":{"givenName":"Charles","familyName":"Leclerc","code":"LEC","nationality":"Monégasque"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"6","points":"156","wins":"0","Driver":{"givenName":"Lewis","familyName":"Hamilton","code":"HAM","nationality":"British"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"7","points":"114","wins":"0","Driver":{"givenName":"Kimi","familyName":"Antonelli","code":"ANT","nationality":"Italian"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"8","points":"96","wins":"0","Driver":{"givenName":"Carlos","familyName":"Sainz","code":"SAI","nationality":"Spanish"},"Constructors":[{"constructorId":"williams","name":"Williams"}]},
        {"position":"9","points":"70","wins":"0","Driver":{"givenName":"Fernando","familyName":"Alonso","code":"ALO","nationality":"Spanish"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
        {"position":"10","points":"65","wins":"0","Driver":{"givenName":"Nico","familyName":"Hülkenberg","code":"HUL","nationality":"German"},"Constructors":[{"constructorId":"kick_sauber","name":"Kick Sauber"}]},
        {"position":"11","points":"58","wins":"0","Driver":{"givenName":"Isack","familyName":"Hadjar","code":"HAD","nationality":"French"},"Constructors":[{"constructorId":"racing_bulls","name":"Racing Bulls"}]},
        {"position":"12","points":"33","wins":"0","Driver":{"givenName":"Yuki","familyName":"Tsunoda","code":"TSU","nationality":"Japanese"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"13","points":"31","wins":"0","Driver":{"givenName":"Liam","familyName":"Lawson","code":"LAW","nationality":"New Zealander"},"Constructors":[{"constructorId":"racing_bulls","name":"Racing Bulls"}]},
        {"position":"14","points":"28","wins":"0","Driver":{"givenName":"Lance","familyName":"Stroll","code":"STR","nationality":"Canadian"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
        {"position":"15","points":"22","wins":"0","Driver":{"givenName":"Esteban","familyName":"Ocon","code":"OCO","nationality":"French"},"Constructors":[{"constructorId":"haas","name":"Haas F1 Team"}]},
        {"position":"16","points":"18","wins":"0","Driver":{"givenName":"Oliver","familyName":"Bearman","code":"BEA","nationality":"British"},"Constructors":[{"constructorId":"haas","name":"Haas F1 Team"}]},
        {"position":"17","points":"16","wins":"0","Driver":{"givenName":"Gabriel","familyName":"Bortoleto","code":"BOR","nationality":"Brazilian"},"Constructors":[{"constructorId":"kick_sauber","name":"Kick Sauber"}]},
        {"position":"18","points":"14","wins":"0","Driver":{"givenName":"Alexander","familyName":"Albon","code":"ALB","nationality":"Thai"},"Constructors":[{"constructorId":"williams","name":"Williams"}]},
        {"position":"19","points":"5","wins":"0","Driver":{"givenName":"Franco","familyName":"Colapinto","code":"COL","nationality":"Argentine"},"Constructors":[{"constructorId":"alpine","name":"Alpine"}]},
        {"position":"20","points":"5","wins":"0","Driver":{"givenName":"Pierre","familyName":"Gasly","code":"GAS","nationality":"French"},"Constructors":[{"constructorId":"alpine","name":"Alpine"}]},
    ],
    "constructor_standings":[
        {"position":"1","points":"833","wins":"13","Constructor":{"constructorId":"mclaren","name":"McLaren","nationality":"British"}},
        {"position":"2","points":"469","wins":"3","Constructor":{"constructorId":"mercedes","name":"Mercedes","nationality":"German"}},
        {"position":"3","points":"451","wins":"8","Constructor":{"constructorId":"red_bull","name":"Red Bull Racing","nationality":"Austrian"}},
        {"position":"4","points":"398","wins":"0","Constructor":{"constructorId":"ferrari","name":"Ferrari","nationality":"Italian"}},
        {"position":"5","points":"166","wins":"0","Constructor":{"constructorId":"williams","name":"Williams","nationality":"British"}},
        {"position":"6","points":"98","wins":"0","Constructor":{"constructorId":"aston_martin","name":"Aston Martin","nationality":"British"}},
        {"position":"7","points":"89","wins":"0","Constructor":{"constructorId":"racing_bulls","name":"Racing Bulls","nationality":"Italian"}},
        {"position":"8","points":"81","wins":"0","Constructor":{"constructorId":"kick_sauber","name":"Kick Sauber","nationality":"Swiss"}},
        {"position":"9","points":"40","wins":"0","Constructor":{"constructorId":"haas","name":"Haas F1 Team","nationality":"American"}},
        {"position":"10","points":"10","wins":"0","Constructor":{"constructorId":"alpine","name":"Alpine","nationality":"French"}},
    ],
    "races":[
        {"round":"1","raceName":"Australian Grand Prix","date":"2025-03-16","Circuit":{"circuitName":"Albert Park Circuit","Location":{"country":"Australia"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"2","raceName":"Chinese Grand Prix","date":"2025-03-23","Circuit":{"circuitName":"Shanghai International Circuit","Location":{"country":"China"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"3","raceName":"Japanese Grand Prix","date":"2025-04-06","Circuit":{"circuitName":"Suzuka International Racing Course","Location":{"country":"Japan"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"4","raceName":"Bahrain Grand Prix","date":"2025-04-13","Circuit":{"circuitName":"Bahrain International Circuit","Location":{"country":"Bahrain"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"5","raceName":"Saudi Arabian Grand Prix","date":"2025-04-20","Circuit":{"circuitName":"Jeddah Corniche Circuit","Location":{"country":"Saudi Arabia"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"6","raceName":"Miami Grand Prix","date":"2025-05-04","Circuit":{"circuitName":"Miami International Autodrome","Location":{"country":"USA"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"7","raceName":"Emilia Romagna Grand Prix","date":"2025-05-18","Circuit":{"circuitName":"Autodromo Enzo e Dino Ferrari","Location":{"country":"Italy"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"8","raceName":"Monaco Grand Prix","date":"2025-05-25","Circuit":{"circuitName":"Circuit de Monaco","Location":{"country":"Monaco"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"9","raceName":"Spanish Grand Prix","date":"2025-06-01","Circuit":{"circuitName":"Circuit de Barcelona-Catalunya","Location":{"country":"Spain"}},"winner":"RUS","winnerFull":"George Russell","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"10","raceName":"Canadian Grand Prix","date":"2025-06-15","Circuit":{"circuitName":"Circuit Gilles Villeneuve","Location":{"country":"Canada"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"11","raceName":"Austrian Grand Prix","date":"2025-06-29","Circuit":{"circuitName":"Red Bull Ring","Location":{"country":"Austria"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"12","raceName":"British Grand Prix","date":"2025-07-06","Circuit":{"circuitName":"Silverstone Circuit","Location":{"country":"UK"}},"winner":"RUS","winnerFull":"George Russell","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"13","raceName":"Belgian Grand Prix","date":"2025-07-27","Circuit":{"circuitName":"Circuit de Spa-Francorchamps","Location":{"country":"Belgium"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"14","raceName":"Hungarian Grand Prix","date":"2025-08-03","Circuit":{"circuitName":"Hungaroring","Location":{"country":"Hungary"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"15","raceName":"Dutch Grand Prix","date":"2025-08-31","Circuit":{"circuitName":"Circuit Zandvoort","Location":{"country":"Netherlands"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"16","raceName":"Italian Grand Prix","date":"2025-09-07","Circuit":{"circuitName":"Autodromo Nazionale Monza","Location":{"country":"Italy"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"17","raceName":"Azerbaijan Grand Prix","date":"2025-09-21","Circuit":{"circuitName":"Baku City Circuit","Location":{"country":"Azerbaijan"}},"winner":"RUS","winnerFull":"George Russell","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"18","raceName":"Singapore Grand Prix","date":"2025-10-05","Circuit":{"circuitName":"Marina Bay Street Circuit","Location":{"country":"Singapore"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"19","raceName":"United States Grand Prix","date":"2025-10-19","Circuit":{"circuitName":"Circuit of the Americas","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"20","raceName":"Mexico City Grand Prix","date":"2025-10-26","Circuit":{"circuitName":"Autodromo Hermanos Rodriguez","Location":{"country":"Mexico"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"21","raceName":"São Paulo Grand Prix","date":"2025-11-09","Circuit":{"circuitName":"Autodromo Jose Carlos Pace","Location":{"country":"Brazil"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"22","raceName":"Las Vegas Grand Prix","date":"2025-11-22","Circuit":{"circuitName":"Las Vegas Strip Street Circuit","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"23","raceName":"Qatar Grand Prix","date":"2025-11-30","Circuit":{"circuitName":"Lusail International Circuit","Location":{"country":"Qatar"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"24","raceName":"Abu Dhabi Grand Prix","date":"2025-12-07","Circuit":{"circuitName":"Yas Marina Circuit","Location":{"country":"Abu Dhabi"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
    ],
    "progression":{"NOR":[25,43,55,67,92,114,139,164,182,194,220,246,271,296,302,308,316,322,322,322,347,347,373,423],"VER":[18,36,61,73,79,91,97,103,109,134,140,146,158,164,189,214,232,257,282,307,313,338,350,421],"PIA":[2,27,39,64,70,95,103,111,119,125,150,162,180,205,211,211,219,225,231,237,249,249,274,410],"RUS":[15,21,27,33,39,51,59,63,88,100,106,131,149,155,161,167,175,181,187,193,199,217,223,319],"LEC":[12,18,24,30,36,42,48,54,60,66,74,82,90,96,108,120,126,132,144,150,158,170,182,242],"HAM":[6,12,18,27,33,39,45,51,57,63,71,79,87,93,99,107,113,119,125,131,131,139,145,156],"ANT":[3,9,15,21,21,27,33,37,43,49,53,57,65,69,77,81,85,91,95,99,101,115,109,114],"SAI":[0,0,6,12,18,26,34,40,46,58,62,66,70,74,78,82,82,82,84,86,90,98,98,96]},
    "race_labels":["AUS","CHN","JPN","BHR","SAU","MIA","IMO","MON","ESP","CAN","AUT","GBR","BEL","HUN","NLD","ITA","AZE","SGP","USA","MEX","SAO","LVG","QAT","ABU"],
},

2024: {
    "champion":"Max Verstappen","champion_team":"Red Bull Racing","ctor_champion":"McLaren",
    "driver_standings":[
        {"position":"1","points":"437","wins":"9","Driver":{"givenName":"Max","familyName":"Verstappen","code":"VER","nationality":"Dutch"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"2","points":"374","wins":"4","Driver":{"givenName":"Lando","familyName":"Norris","code":"NOR","nationality":"British"},"Constructors":[{"constructorId":"mclaren","name":"McLaren"}]},
        {"position":"3","points":"356","wins":"3","Driver":{"givenName":"Charles","familyName":"Leclerc","code":"LEC","nationality":"Monégasque"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"4","points":"292","wins":"2","Driver":{"givenName":"Oscar","familyName":"Piastri","code":"PIA","nationality":"Australian"},"Constructors":[{"constructorId":"mclaren","name":"McLaren"}]},
        {"position":"5","points":"290","wins":"2","Driver":{"givenName":"Carlos","familyName":"Sainz","code":"SAI","nationality":"Spanish"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"6","points":"192","wins":"0","Driver":{"givenName":"Sergio","familyName":"Pérez","code":"PER","nationality":"Mexican"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"7","points":"177","wins":"2","Driver":{"givenName":"George","familyName":"Russell","code":"RUS","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"8","points":"174","wins":"2","Driver":{"givenName":"Lewis","familyName":"Hamilton","code":"HAM","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"9","points":"97","wins":"0","Driver":{"givenName":"Fernando","familyName":"Alonso","code":"ALO","nationality":"Spanish"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
        {"position":"10","points":"59","wins":"0","Driver":{"givenName":"Lance","familyName":"Stroll","code":"STR","nationality":"Canadian"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
        {"position":"11","points":"50","wins":"0","Driver":{"givenName":"Nico","familyName":"Hülkenberg","code":"HUL","nationality":"German"},"Constructors":[{"constructorId":"haas","name":"Haas F1 Team"}]},
        {"position":"12","points":"44","wins":"0","Driver":{"givenName":"Yuki","familyName":"Tsunoda","code":"TSU","nationality":"Japanese"},"Constructors":[{"constructorId":"rb","name":"RB"}]},
        {"position":"13","points":"40","wins":"0","Driver":{"givenName":"Esteban","familyName":"Ocon","code":"OCO","nationality":"French"},"Constructors":[{"constructorId":"alpine","name":"Alpine"}]},
        {"position":"14","points":"33","wins":"0","Driver":{"givenName":"Pierre","familyName":"Gasly","code":"GAS","nationality":"French"},"Constructors":[{"constructorId":"alpine","name":"Alpine"}]},
        {"position":"15","points":"24","wins":"0","Driver":{"givenName":"Oliver","familyName":"Bearman","code":"BEA","nationality":"British"},"Constructors":[{"constructorId":"haas","name":"Haas F1 Team"}]},
        {"position":"16","points":"22","wins":"0","Driver":{"givenName":"Kevin","familyName":"Magnussen","code":"MAG","nationality":"Danish"},"Constructors":[{"constructorId":"haas","name":"Haas F1 Team"}]},
        {"position":"17","points":"14","wins":"0","Driver":{"givenName":"Alexander","familyName":"Albon","code":"ALB","nationality":"Thai"},"Constructors":[{"constructorId":"williams","name":"Williams"}]},
        {"position":"18","points":"12","wins":"0","Driver":{"givenName":"Daniel","familyName":"Ricciardo","code":"RIC","nationality":"Australian"},"Constructors":[{"constructorId":"rb","name":"RB"}]},
        {"position":"19","points":"6","wins":"0","Driver":{"givenName":"Liam","familyName":"Lawson","code":"LAW","nationality":"New Zealander"},"Constructors":[{"constructorId":"rb","name":"RB"}]},
        {"position":"20","points":"6","wins":"0","Driver":{"givenName":"Franco","familyName":"Colapinto","code":"COL","nationality":"Argentine"},"Constructors":[{"constructorId":"williams","name":"Williams"}]},
    ],
    "constructor_standings":[
        {"position":"1","points":"666","wins":"6","Constructor":{"constructorId":"mclaren","name":"McLaren","nationality":"British"}},
        {"position":"2","points":"652","wins":"5","Constructor":{"constructorId":"ferrari","name":"Ferrari","nationality":"Italian"}},
        {"position":"3","points":"589","wins":"9","Constructor":{"constructorId":"red_bull","name":"Red Bull Racing","nationality":"Austrian"}},
        {"position":"4","points":"468","wins":"4","Constructor":{"constructorId":"mercedes","name":"Mercedes","nationality":"German"}},
        {"position":"5","points":"94","wins":"0","Constructor":{"constructorId":"aston_martin","name":"Aston Martin","nationality":"British"}},
        {"position":"6","points":"65","wins":"0","Constructor":{"constructorId":"alpine","name":"Alpine","nationality":"French"}},
        {"position":"7","points":"58","wins":"0","Constructor":{"constructorId":"haas","name":"Haas F1 Team","nationality":"American"}},
        {"position":"8","points":"46","wins":"0","Constructor":{"constructorId":"rb","name":"RB","nationality":"Italian"}},
        {"position":"9","points":"17","wins":"0","Constructor":{"constructorId":"williams","name":"Williams","nationality":"British"}},
        {"position":"10","points":"4","wins":"0","Constructor":{"constructorId":"kick_sauber","name":"Kick Sauber","nationality":"Swiss"}},
    ],
    "races":[
        {"round":"1","raceName":"Bahrain Grand Prix","date":"2024-03-02","Circuit":{"circuitName":"Bahrain International Circuit","Location":{"country":"Bahrain"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"2","raceName":"Saudi Arabian Grand Prix","date":"2024-03-09","Circuit":{"circuitName":"Jeddah Corniche Circuit","Location":{"country":"Saudi Arabia"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"3","raceName":"Australian Grand Prix","date":"2024-03-24","Circuit":{"circuitName":"Albert Park Circuit","Location":{"country":"Australia"}},"winner":"SAI","winnerFull":"Carlos Sainz","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"4","raceName":"Japanese Grand Prix","date":"2024-04-07","Circuit":{"circuitName":"Suzuka International Racing Course","Location":{"country":"Japan"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"5","raceName":"Chinese Grand Prix","date":"2024-04-21","Circuit":{"circuitName":"Shanghai International Circuit","Location":{"country":"China"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"6","raceName":"Miami Grand Prix","date":"2024-05-05","Circuit":{"circuitName":"Miami International Autodrome","Location":{"country":"USA"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"7","raceName":"Emilia Romagna Grand Prix","date":"2024-05-19","Circuit":{"circuitName":"Autodromo Enzo e Dino Ferrari","Location":{"country":"Italy"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"8","raceName":"Monaco Grand Prix","date":"2024-05-26","Circuit":{"circuitName":"Circuit de Monaco","Location":{"country":"Monaco"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"9","raceName":"Canadian Grand Prix","date":"2024-06-09","Circuit":{"circuitName":"Circuit Gilles Villeneuve","Location":{"country":"Canada"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"10","raceName":"Spanish Grand Prix","date":"2024-06-23","Circuit":{"circuitName":"Circuit de Barcelona-Catalunya","Location":{"country":"Spain"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"11","raceName":"Austrian Grand Prix","date":"2024-06-30","Circuit":{"circuitName":"Red Bull Ring","Location":{"country":"Austria"}},"winner":"RUS","winnerFull":"George Russell","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"12","raceName":"British Grand Prix","date":"2024-07-07","Circuit":{"circuitName":"Silverstone Circuit","Location":{"country":"UK"}},"winner":"HAM","winnerFull":"Lewis Hamilton","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"13","raceName":"Hungarian Grand Prix","date":"2024-07-21","Circuit":{"circuitName":"Hungaroring","Location":{"country":"Hungary"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"14","raceName":"Belgian Grand Prix","date":"2024-07-28","Circuit":{"circuitName":"Circuit de Spa-Francorchamps","Location":{"country":"Belgium"}},"winner":"HAM","winnerFull":"Lewis Hamilton","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"15","raceName":"Dutch Grand Prix","date":"2024-08-25","Circuit":{"circuitName":"Circuit Zandvoort","Location":{"country":"Netherlands"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"16","raceName":"Italian Grand Prix","date":"2024-09-01","Circuit":{"circuitName":"Autodromo Nazionale Monza","Location":{"country":"Italy"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"17","raceName":"Azerbaijan Grand Prix","date":"2024-09-15","Circuit":{"circuitName":"Baku City Circuit","Location":{"country":"Azerbaijan"}},"winner":"PIA","winnerFull":"Oscar Piastri","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"18","raceName":"Singapore Grand Prix","date":"2024-09-22","Circuit":{"circuitName":"Marina Bay Street Circuit","Location":{"country":"Singapore"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"19","raceName":"United States Grand Prix","date":"2024-10-20","Circuit":{"circuitName":"Circuit of the Americas","Location":{"country":"USA"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"20","raceName":"Mexico City Grand Prix","date":"2024-10-27","Circuit":{"circuitName":"Autodromo Hermanos Rodriguez","Location":{"country":"Mexico"}},"winner":"SAI","winnerFull":"Carlos Sainz","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"21","raceName":"São Paulo Grand Prix","date":"2024-11-03","Circuit":{"circuitName":"Autodromo Jose Carlos Pace","Location":{"country":"Brazil"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"22","raceName":"Las Vegas Grand Prix","date":"2024-11-23","Circuit":{"circuitName":"Las Vegas Strip Street Circuit","Location":{"country":"USA"}},"winner":"RUS","winnerFull":"George Russell","team":"Mercedes","results":[],"sprint_results":[]},
        {"round":"23","raceName":"Qatar Grand Prix","date":"2024-12-01","Circuit":{"circuitName":"Lusail International Circuit","Location":{"country":"Qatar"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"24","raceName":"Abu Dhabi Grand Prix","date":"2024-12-08","Circuit":{"circuitName":"Yas Marina Circuit","Location":{"country":"Abu Dhabi"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
    ],
    "progression":{"VER":[26,51,51,77,110,110,160,160,194,219,225,225,229,235,249,249,255,273,298,298,331,356,369,437],"NOR":[6,21,21,21,34,59,65,71,71,78,90,108,126,140,168,168,174,198,215,222,240,263,298,374],"LEC":[12,27,33,39,45,51,57,94,94,101,107,113,125,131,147,172,178,184,209,215,221,231,234,356],"PIA":[9,24,24,30,42,48,54,60,66,74,86,104,120,126,154,154,164,176,176,198,204,210,222,292],"SAI":[15,21,33,45,51,57,63,63,63,70,82,96,104,118,130,138,144,150,157,182,184,188,192,290],"PER":[18,36,44,50,56,58,110,110,138,150,152,152,152,152,152,152,155,159,159,159,161,165,168,192],"RUS":[4,10,10,10,16,22,28,34,40,46,62,74,82,82,90,96,96,96,96,96,96,122,128,177],"HAM":[0,4,12,12,18,24,30,36,42,48,54,60,68,98,98,98,104,106,108,110,110,116,122,174]},
    "race_labels":["BHR","SAU","AUS","JPN","CHN","MIA","IMO","MON","CAN","ESP","AUT","GBR","HUN","BEL","NLD","ITA","AZE","SGP","USA","MEX","SAO","LVG","QAT","ABU"],
},

2023: {
    "champion":"Max Verstappen","champion_team":"Red Bull Racing","ctor_champion":"Red Bull Racing",
    "driver_standings":[
        {"position":"1","points":"575","wins":"19","Driver":{"givenName":"Max","familyName":"Verstappen","code":"VER","nationality":"Dutch"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"2","points":"285","wins":"2","Driver":{"givenName":"Sergio","familyName":"Pérez","code":"PER","nationality":"Mexican"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"3","points":"234","wins":"0","Driver":{"givenName":"Fernando","familyName":"Alonso","code":"ALO","nationality":"Spanish"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
        {"position":"4","points":"206","wins":"1","Driver":{"givenName":"Lewis","familyName":"Hamilton","code":"HAM","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"5","points":"205","wins":"1","Driver":{"givenName":"Carlos","familyName":"Sainz","code":"SAI","nationality":"Spanish"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"6","points":"200","wins":"0","Driver":{"givenName":"George","familyName":"Russell","code":"RUS","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"7","points":"206","wins":"0","Driver":{"givenName":"Charles","familyName":"Leclerc","code":"LEC","nationality":"Monégasque"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"8","points":"97","wins":"0","Driver":{"givenName":"Lando","familyName":"Norris","code":"NOR","nationality":"British"},"Constructors":[{"constructorId":"mclaren","name":"McLaren"}]},
        {"position":"9","points":"74","wins":"0","Driver":{"givenName":"Oscar","familyName":"Piastri","code":"PIA","nationality":"Australian"},"Constructors":[{"constructorId":"mclaren","name":"McLaren"}]},
        {"position":"10","points":"69","wins":"0","Driver":{"givenName":"Lance","familyName":"Stroll","code":"STR","nationality":"Canadian"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
    ],
    "constructor_standings":[
        {"position":"1","points":"860","wins":"21","Constructor":{"constructorId":"red_bull","name":"Red Bull Racing","nationality":"Austrian"}},
        {"position":"2","points":"409","wins":"1","Constructor":{"constructorId":"mercedes","name":"Mercedes","nationality":"German"}},
        {"position":"3","points":"406","wins":"1","Constructor":{"constructorId":"ferrari","name":"Ferrari","nationality":"Italian"}},
        {"position":"4","points":"280","wins":"0","Constructor":{"constructorId":"aston_martin","name":"Aston Martin","nationality":"British"}},
        {"position":"5","points":"302","wins":"0","Constructor":{"constructorId":"mclaren","name":"McLaren","nationality":"British"}},
        {"position":"6","points":"57","wins":"0","Constructor":{"constructorId":"alpine","name":"Alpine","nationality":"French"}},
        {"position":"7","points":"47","wins":"0","Constructor":{"constructorId":"williams","name":"Williams","nationality":"British"}},
        {"position":"8","points":"29","wins":"0","Constructor":{"constructorId":"alphatauri","name":"AlphaTauri","nationality":"Italian"}},
        {"position":"9","points":"16","wins":"0","Constructor":{"constructorId":"alfa","name":"Alfa Romeo","nationality":"Swiss"}},
        {"position":"10","points":"12","wins":"0","Constructor":{"constructorId":"haas","name":"Haas F1 Team","nationality":"American"}},
    ],
    "races":[
        {"round":"1","raceName":"Bahrain Grand Prix","date":"2023-03-05","Circuit":{"circuitName":"Bahrain International Circuit","Location":{"country":"Bahrain"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"2","raceName":"Saudi Arabian Grand Prix","date":"2023-03-19","Circuit":{"circuitName":"Jeddah Corniche Circuit","Location":{"country":"Saudi Arabia"}},"winner":"PER","winnerFull":"Sergio Pérez","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"3","raceName":"Australian Grand Prix","date":"2023-04-02","Circuit":{"circuitName":"Albert Park Circuit","Location":{"country":"Australia"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"4","raceName":"Azerbaijan Grand Prix","date":"2023-04-30","Circuit":{"circuitName":"Baku City Circuit","Location":{"country":"Azerbaijan"}},"winner":"PER","winnerFull":"Sergio Pérez","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"5","raceName":"Miami Grand Prix","date":"2023-05-07","Circuit":{"circuitName":"Miami International Autodrome","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"6","raceName":"Monaco Grand Prix","date":"2023-05-28","Circuit":{"circuitName":"Circuit de Monaco","Location":{"country":"Monaco"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"7","raceName":"Spanish Grand Prix","date":"2023-06-04","Circuit":{"circuitName":"Circuit de Barcelona-Catalunya","Location":{"country":"Spain"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"8","raceName":"Canadian Grand Prix","date":"2023-06-18","Circuit":{"circuitName":"Circuit Gilles Villeneuve","Location":{"country":"Canada"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"9","raceName":"Austrian Grand Prix","date":"2023-07-02","Circuit":{"circuitName":"Red Bull Ring","Location":{"country":"Austria"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"10","raceName":"British Grand Prix","date":"2023-07-09","Circuit":{"circuitName":"Silverstone Circuit","Location":{"country":"UK"}},"winner":"NOR","winnerFull":"Lando Norris","team":"McLaren","results":[],"sprint_results":[]},
        {"round":"11","raceName":"Hungarian Grand Prix","date":"2023-07-23","Circuit":{"circuitName":"Hungaroring","Location":{"country":"Hungary"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"12","raceName":"Belgian Grand Prix","date":"2023-07-30","Circuit":{"circuitName":"Circuit de Spa-Francorchamps","Location":{"country":"Belgium"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"13","raceName":"Dutch Grand Prix","date":"2023-08-27","Circuit":{"circuitName":"Circuit Zandvoort","Location":{"country":"Netherlands"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"14","raceName":"Italian Grand Prix","date":"2023-09-03","Circuit":{"circuitName":"Autodromo Nazionale Monza","Location":{"country":"Italy"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"15","raceName":"Singapore Grand Prix","date":"2023-09-17","Circuit":{"circuitName":"Marina Bay Street Circuit","Location":{"country":"Singapore"}},"winner":"SAI","winnerFull":"Carlos Sainz","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"16","raceName":"Japanese Grand Prix","date":"2023-09-24","Circuit":{"circuitName":"Suzuka International Racing Course","Location":{"country":"Japan"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"17","raceName":"Qatar Grand Prix","date":"2023-10-08","Circuit":{"circuitName":"Lusail International Circuit","Location":{"country":"Qatar"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"18","raceName":"United States Grand Prix","date":"2023-10-22","Circuit":{"circuitName":"Circuit of the Americas","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"19","raceName":"Mexico City Grand Prix","date":"2023-10-29","Circuit":{"circuitName":"Autodromo Hermanos Rodriguez","Location":{"country":"Mexico"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"20","raceName":"São Paulo Grand Prix","date":"2023-11-05","Circuit":{"circuitName":"Autodromo Jose Carlos Pace","Location":{"country":"Brazil"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"21","raceName":"Las Vegas Grand Prix","date":"2023-11-18","Circuit":{"circuitName":"Las Vegas Strip Street Circuit","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"22","raceName":"Abu Dhabi Grand Prix","date":"2023-11-26","Circuit":{"circuitName":"Yas Marina Circuit","Location":{"country":"Abu Dhabi"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
    ],
    "progression":{"VER":[25,44,69,94,119,144,170,195,220,220,255,274,294,312,312,337,362,387,412,437,462,575],"PER":[6,31,43,74,80,92,104,116,128,132,144,156,163,171,179,179,185,191,197,200,206,285],"ALO":[15,27,39,45,57,63,75,87,105,111,117,125,131,139,147,153,159,165,171,177,183,234],"HAM":[0,8,14,20,26,26,32,38,44,56,68,74,82,94,94,94,100,106,112,122,128,206],"SAI":[6,12,20,26,32,38,44,50,56,68,74,80,86,92,118,118,124,130,140,150,162,205],"NOR":[0,0,4,4,4,8,12,14,16,32,38,40,52,58,64,64,64,64,70,76,76,97]},
    "race_labels":["BHR","SAU","AUS","AZE","MIA","MON","ESP","CAN","AUT","GBR","HUN","BEL","NLD","ITA","SGP","JPN","QAT","USA","MEX","SAO","LVG","ABU"],
},

2022: {
    "champion":"Max Verstappen","champion_team":"Red Bull Racing","ctor_champion":"Red Bull Racing",
    "driver_standings":[
        {"position":"1","points":"454","wins":"15","Driver":{"givenName":"Max","familyName":"Verstappen","code":"VER","nationality":"Dutch"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"2","points":"308","wins":"2","Driver":{"givenName":"Charles","familyName":"Leclerc","code":"LEC","nationality":"Monégasque"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"3","points":"305","wins":"2","Driver":{"givenName":"Sergio","familyName":"Pérez","code":"PER","nationality":"Mexican"},"Constructors":[{"constructorId":"red_bull","name":"Red Bull Racing"}]},
        {"position":"4","points":"275","wins":"1","Driver":{"givenName":"George","familyName":"Russell","code":"RUS","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"5","points":"265","wins":"1","Driver":{"givenName":"Carlos","familyName":"Sainz","code":"SAI","nationality":"Spanish"},"Constructors":[{"constructorId":"ferrari","name":"Ferrari"}]},
        {"position":"6","points":"240","wins":"0","Driver":{"givenName":"Lewis","familyName":"Hamilton","code":"HAM","nationality":"British"},"Constructors":[{"constructorId":"mercedes","name":"Mercedes"}]},
        {"position":"7","points":"88","wins":"0","Driver":{"givenName":"Valtteri","familyName":"Bottas","code":"BOT","nationality":"Finnish"},"Constructors":[{"constructorId":"alfa","name":"Alfa Romeo"}]},
        {"position":"8","points":"92","wins":"0","Driver":{"givenName":"Esteban","familyName":"Ocon","code":"OCO","nationality":"French"},"Constructors":[{"constructorId":"alpine","name":"Alpine"}]},
        {"position":"9","points":"138","wins":"0","Driver":{"givenName":"Sebastian","familyName":"Vettel","code":"VET","nationality":"German"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
        {"position":"10","points":"127","wins":"0","Driver":{"givenName":"Lance","familyName":"Stroll","code":"STR","nationality":"Canadian"},"Constructors":[{"constructorId":"aston_martin","name":"Aston Martin"}]},
    ],
    "constructor_standings":[
        {"position":"1","points":"759","wins":"17","Constructor":{"constructorId":"red_bull","name":"Red Bull Racing","nationality":"Austrian"}},
        {"position":"2","points":"554","wins":"4","Constructor":{"constructorId":"ferrari","name":"Ferrari","nationality":"Italian"}},
        {"position":"3","points":"515","wins":"1","Constructor":{"constructorId":"mercedes","name":"Mercedes","nationality":"German"}},
        {"position":"4","points":"292","wins":"0","Constructor":{"constructorId":"alpine","name":"Alpine","nationality":"French"}},
        {"position":"5","points":"246","wins":"0","Constructor":{"constructorId":"mclaren","name":"McLaren","nationality":"British"}},
        {"position":"6","points":"224","wins":"0","Constructor":{"constructorId":"alfa","name":"Alfa Romeo","nationality":"Swiss"}},
        {"position":"7","points":"138","wins":"0","Constructor":{"constructorId":"aston_martin","name":"Aston Martin","nationality":"British"}},
        {"position":"8","points":"37","wins":"0","Constructor":{"constructorId":"haas","name":"Haas F1 Team","nationality":"American"}},
        {"position":"9","points":"35","wins":"0","Constructor":{"constructorId":"alphatauri","name":"AlphaTauri","nationality":"Italian"}},
        {"position":"10","points":"8","wins":"0","Constructor":{"constructorId":"williams","name":"Williams","nationality":"British"}},
    ],
    "races":[
        {"round":"1","raceName":"Bahrain Grand Prix","date":"2022-03-20","Circuit":{"circuitName":"Bahrain International Circuit","Location":{"country":"Bahrain"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"2","raceName":"Saudi Arabian Grand Prix","date":"2022-03-27","Circuit":{"circuitName":"Jeddah Corniche Circuit","Location":{"country":"Saudi Arabia"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"3","raceName":"Australian Grand Prix","date":"2022-04-10","Circuit":{"circuitName":"Albert Park Circuit","Location":{"country":"Australia"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"4","raceName":"Emilia Romagna Grand Prix","date":"2022-04-24","Circuit":{"circuitName":"Autodromo Enzo e Dino Ferrari","Location":{"country":"Italy"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"5","raceName":"Miami Grand Prix","date":"2022-05-08","Circuit":{"circuitName":"Miami International Autodrome","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"6","raceName":"Spanish Grand Prix","date":"2022-05-22","Circuit":{"circuitName":"Circuit de Barcelona-Catalunya","Location":{"country":"Spain"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"7","raceName":"Monaco Grand Prix","date":"2022-05-29","Circuit":{"circuitName":"Circuit de Monaco","Location":{"country":"Monaco"}},"winner":"PER","winnerFull":"Sergio Pérez","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"8","raceName":"Azerbaijan Grand Prix","date":"2022-06-12","Circuit":{"circuitName":"Baku City Circuit","Location":{"country":"Azerbaijan"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"9","raceName":"Canadian Grand Prix","date":"2022-06-19","Circuit":{"circuitName":"Circuit Gilles Villeneuve","Location":{"country":"Canada"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"10","raceName":"British Grand Prix","date":"2022-07-03","Circuit":{"circuitName":"Silverstone Circuit","Location":{"country":"UK"}},"winner":"SAI","winnerFull":"Carlos Sainz","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"11","raceName":"Austrian Grand Prix","date":"2022-07-10","Circuit":{"circuitName":"Red Bull Ring","Location":{"country":"Austria"}},"winner":"LEC","winnerFull":"Charles Leclerc","team":"Ferrari","results":[],"sprint_results":[]},
        {"round":"12","raceName":"French Grand Prix","date":"2022-07-24","Circuit":{"circuitName":"Circuit Paul Ricard","Location":{"country":"France"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"13","raceName":"Hungarian Grand Prix","date":"2022-07-31","Circuit":{"circuitName":"Hungaroring","Location":{"country":"Hungary"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"14","raceName":"Belgian Grand Prix","date":"2022-08-28","Circuit":{"circuitName":"Circuit de Spa-Francorchamps","Location":{"country":"Belgium"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"15","raceName":"Dutch Grand Prix","date":"2022-09-04","Circuit":{"circuitName":"Circuit Zandvoort","Location":{"country":"Netherlands"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"16","raceName":"Italian Grand Prix","date":"2022-09-11","Circuit":{"circuitName":"Autodromo Nazionale Monza","Location":{"country":"Italy"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"17","raceName":"Singapore Grand Prix","date":"2022-10-02","Circuit":{"circuitName":"Marina Bay Street Circuit","Location":{"country":"Singapore"}},"winner":"PER","winnerFull":"Sergio Pérez","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"18","raceName":"Japanese Grand Prix","date":"2022-10-09","Circuit":{"circuitName":"Suzuka International Racing Course","Location":{"country":"Japan"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"19","raceName":"United States Grand Prix","date":"2022-10-23","Circuit":{"circuitName":"Circuit of the Americas","Location":{"country":"USA"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"20","raceName":"Mexico City Grand Prix","date":"2022-10-30","Circuit":{"circuitName":"Autodromo Hermanos Rodriguez","Location":{"country":"Mexico"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"21","raceName":"São Paulo Grand Prix","date":"2022-11-13","Circuit":{"circuitName":"Autodromo Jose Carlos Pace","Location":{"country":"Brazil"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
        {"round":"22","raceName":"Abu Dhabi Grand Prix","date":"2022-11-20","Circuit":{"circuitName":"Yas Marina Circuit","Location":{"country":"Abu Dhabi"}},"winner":"VER","winnerFull":"Max Verstappen","team":"Red Bull Racing","results":[],"sprint_results":[]},
    ],
    "progression":{"VER":[26,45,71,87,103,116,122,138,157,157,163,182,200,219,244,263,272,281,300,319,337,454],"LEC":[26,51,71,71,71,78,78,78,78,84,98,98,104,104,104,116,116,116,116,116,116,308],"PER":[18,30,30,36,48,54,84,100,110,110,116,122,128,134,139,145,175,195,207,220,226,305],"RUS":[0,4,14,20,26,38,44,56,62,74,86,94,106,112,120,128,134,140,148,156,165,275],"SAI":[0,15,30,30,38,50,54,54,60,85,85,91,99,105,105,111,111,111,111,119,127,265],"HAM":[0,9,15,21,27,33,39,39,47,47,47,56,59,74,80,80,80,86,95,104,113,240]},
    "race_labels":["BHR","SAU","AUS","IMO","MIA","ESP","MON","AZE","CAN","GBR","AUT","FRA","HUN","BEL","NLD","ITA","SGP","JPN","USA","MEX","SAO","ABU"],
},

}

# ─────────────────────────────────────────────────────────────────────────────
# LIVE FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch(path):
    url = f"{BASE_URL}/{path}/?limit=100"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json().get("MRData", {})

def fetch_all_races(season):
    """Paginate through all race results for a season (20 drivers x 24 races = up to 480 rows)."""
    all_races = {}  # round -> race dict with results list
    offset = 0
    limit = 100

    while True:
        url = f"{BASE_URL}/{season}/results/?limit={limit}&offset={offset}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json().get("MRData", {})
        races_page = data.get("RaceTable", {}).get("Races", [])
        total = int(data.get("total", 0))

        if not races_page:
            break

        for race in races_page:
            rnd = race.get("round")
            if rnd not in all_races:
                all_races[rnd] = {k: v for k, v in race.items() if k != "Results"}
                all_races[rnd]["Results"] = []
            all_races[rnd]["Results"].extend(race.get("Results", []))

        offset += limit
        if offset >= total:
            break

        time.sleep(0.3)

    # Return sorted by round number
    return [all_races[k] for k in sorted(all_races.keys(), key=lambda x: int(x))]

def fetch_all_sprints(season):
    """Fetch all sprint results for a season, paginating as needed. Returns dict keyed by round."""
    sprint_map = {}
    offset = 0
    limit = 100

    while True:
        url = f"{BASE_URL}/{season}/sprint/?limit={limit}&offset={offset}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json().get("MRData", {})
        races_page = data.get("RaceTable", {}).get("Races", [])
        total = int(data.get("total", 0))

        if total == 0 or not races_page:
            break  # season has no sprints

        for race in races_page:
            rnd = race.get("round")
            if rnd not in sprint_map:
                sprint_map[rnd] = []
            sprint_map[rnd].extend(race.get("SprintResults", []))

        offset += limit
        if offset >= total:
            break

        time.sleep(0.3)

    return sprint_map  # {round: [SprintResult, ...]}

def slim_result(r):
    """Keep only the fields we need per driver result to keep file size reasonable."""
    return {
        "position": r.get("position",""),
        "grid": r.get("grid",""),
        "points": r.get("points",""),
        "laps": r.get("laps",""),
        "status": r.get("status",""),
        "FastestLap": {"rank": r.get("FastestLap",{}).get("rank",""), "Time": {"time": r.get("FastestLap",{}).get("Time",{}).get("time","")}},
        "Driver": {
            "code": r.get("Driver",{}).get("code",""),
            "givenName": r.get("Driver",{}).get("givenName",""),
            "familyName": r.get("Driver",{}).get("familyName",""),
        },
        "Constructor": {
            "constructorId": r.get("Constructor",{}).get("constructorId",""),
            "name": r.get("Constructor",{}).get("name",""),
        },
    }

def fetch_season(season):
    print(f"\n  [{season}] Fetching driver standings...")
    d_raw = fetch(f"{season}/driverstandings")
    driver_standings = d_raw.get("StandingsTable",{}).get("StandingsLists",[{}])[0].get("DriverStandings",[])

    print(f"  [{season}] Fetching constructor standings...")
    c_raw = fetch(f"{season}/constructorstandings")
    constructor_standings = c_raw.get("StandingsTable",{}).get("StandingsLists",[{}])[0].get("ConstructorStandings",[])

    print(f"  [{season}] Fetching all race results (paginating)...")
    all_races_raw = fetch_all_races(season)

    print(f"  [{season}] Fetching sprint results...")
    sprint_map = fetch_all_sprints(season)
    if sprint_map:
        print(f"    Found sprints at rounds: {sorted(sprint_map.keys())}")
    else:
        print(f"    No sprints found for {season}")

    races = []
    driver_map = {}
    race_labels = []

    for i, race in enumerate(all_races_raw):
        short = race.get("raceName","").replace(" Grand Prix","")[:4].upper()
        race_labels.append(short)
        raw_results = race.get("Results",[])
        winner = raw_results[0] if raw_results else {}

        # Slim down results to just what we display
        results = [slim_result(r) for r in raw_results]

        # Attach sprint results for this round if they exist
        rnd = race.get("round")
        raw_sprint = sprint_map.get(rnd, [])
        sprint_results = [slim_result(r) for r in raw_sprint]

        races.append({
            "round": rnd,
            "raceName": race.get("raceName"),
            "date": race.get("date"),
            "Circuit": race.get("Circuit",{}),
            "winner": winner.get("Driver",{}).get("code",""),
            "winnerFull": f"{winner.get('Driver',{}).get('givenName','')} {winner.get('Driver',{}).get('familyName','')}".strip(),
            "team": winner.get("Constructor",{}).get("name",""),
            "results": results,
            "sprint_results": sprint_results,
        })

        for r in raw_results:
            code = r.get("Driver",{}).get("code") or r.get("Driver",{}).get("familyName","")[:3].upper()
            if code not in driver_map:
                driver_map[code] = {"cumul":0,"points":[]}
            driver_map[code]["cumul"] += float(r.get("points",0))
            driver_map[code]["points"].append(round(driver_map[code]["cumul"],1))

        print(f"    Round {race.get('round'):>2} — {race.get('raceName')} ✓")
        time.sleep(0.3)  # be polite to the API

    progression = {k: v["points"] for k,v in driver_map.items()}
    champion_s = driver_standings[0] if driver_standings else {}
    ctor_s = constructor_standings[0] if constructor_standings else {}

    return {
        "champion": f"{champion_s.get('Driver',{}).get('givenName','')} {champion_s.get('Driver',{}).get('familyName','')}".strip(),
        "champion_team": champion_s.get("Constructors",[{}])[0].get("name",""),
        "ctor_champion": ctor_s.get("Constructor",{}).get("name",""),
        "driver_standings": driver_standings,
        "constructor_standings": constructor_standings,
        "races": races,
        "progression": progression,
        "race_labels": race_labels,
    }

# ─────────────────────────────────────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_html(all_seasons_data, generated_at):
    seasons = sorted(all_seasons_data.keys(), reverse=True)
    default_season = seasons[0]

    js_data_blocks = "\n".join(
        f"  seasonsData[{s}] = {json.dumps(all_seasons_data[s], ensure_ascii=False, separators=(',',':'))};"
        for s in seasons
    )

    season_btn_html = "\n".join(
        f'<button class="season-btn{" active" if s == default_season else ""}" onclick="switchSeason({s})">{s}</button>'
        for s in seasons
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Formula One Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700;800;900&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#08080d;color:#e8e8e8;font-family:'Barlow Condensed','Oswald',sans-serif;min-height:100vh}}
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:#08080d}}
::-webkit-scrollbar-thumb{{background:#e8002d;border-radius:2px}}
.header{{border-bottom:1px solid #141420;background:rgba(8,8,13,.97);backdrop-filter:blur(12px);position:sticky;top:0;z-index:100}}
.header-inner{{max-width:1200px;margin:0 auto;padding:0 24px}}
.logo-text{{font-size:24px;font-weight:900;letter-spacing:.1em}}
.logo-text span{{color:#e8002d}}
.back-link{{display:inline-flex;align-items:center;gap:6px;font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#888;text-decoration:none;transition:color .15s}}
.back-link:hover{{color:#e8002d}}
.back-link svg{{transition:transform .15s}}
.back-link:hover svg{{transform:translateX(-2px)}}
.top-bar{{display:flex;align-items:center;justify-content:space-between;padding:14px 0 10px}}
.season-btns{{display:flex;gap:6px;align-items:center}}
.season-btn{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#888;font-family:inherit;font-size:13px;font-weight:700;letter-spacing:.08em;padding:6px 14px;border-radius:4px;cursor:pointer;transition:all .15s}}
.season-btn:hover{{color:#fff;border-color:#555}}
.season-btn.active{{background:#e8002d;border-color:#e8002d;color:#fff}}
.tabs{{display:flex}}
.tab-btn{{background:none;border:none;color:#555;font-family:inherit;font-size:12px;font-weight:700;letter-spacing:.12em;padding:10px 22px;cursor:pointer;position:relative;transition:color .2s}}
.tab-btn::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;background:#e8002d;transform:scaleX(0);transition:transform .2s}}
.tab-btn.active{{color:#fff}}
.tab-btn.active::after{{transform:scaleX(1)}}
.body{{max-width:1200px;margin:0 auto;padding:28px 24px}}
.tab-content{{display:none}}
.tab-content.active{{display:block}}
.sub-btns{{display:flex;gap:8px;margin-bottom:24px}}
.sub-btn{{background:rgba(255,255,255,.05);border:none;color:#fff;font-family:inherit;font-size:12px;font-weight:700;letter-spacing:.1em;padding:8px 20px;border-radius:4px;cursor:pointer;transition:background .2s}}
.sub-btn.active{{background:#e8002d}}
.card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:8px}}
.standing-row{{padding:14px 20px;margin-bottom:4px;position:relative;overflow:hidden;border-radius:6px;border:1px solid rgba(255,255,255,.07);background:rgba(255,255,255,.025);transition:background .12s}}
.standing-row:hover{{background:rgba(255,255,255,.04)!important}}
.race-item{{padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.04);display:flex;align-items:center;gap:12px;cursor:pointer;border-left:2px solid transparent;transition:all .12s}}
.race-item:hover{{background:rgba(232,0,45,.06)}}
.race-item.selected{{background:rgba(232,0,45,.1);border-left:2px solid #e8002d}}
.pill{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);border-radius:4px;padding:2px 8px;font-size:11px;color:#888}}
.champ-banner{{background:linear-gradient(135deg,rgba(232,0,45,.12),rgba(255,128,0,.06));border:1px solid rgba(232,0,45,.2);border-radius:8px;padding:16px 24px;margin-bottom:24px;display:flex;align-items:center;gap:20px}}
.results-hdr{{display:grid;grid-template-columns:40px 16px 1fr 150px 90px 48px 52px;padding:10px 18px;border-bottom:1px solid rgba(255,255,255,.07);font-size:10px;font-weight:700;letter-spacing:.1em;color:#444}}
.results-row{{display:grid;grid-template-columns:40px 16px 1fr 150px 90px 48px 52px;padding:9px 18px;border-bottom:1px solid rgba(255,255,255,.03);align-items:center;transition:background .1s}}
.results-row:hover{{background:rgba(255,255,255,.02)}}
.race-grid{{display:grid;grid-template-columns:270px 1fr;gap:20px;align-items:start}}
.race-sidebar{{position:sticky;top:80px}}
.race-list{{max-height:600px;overflow-y:auto}}
.no-data{{padding:48px;text-align:center;color:#444;font-family:Barlow,sans-serif;font-size:14px}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.fade{{animation:fadeUp .3s ease forwards}}
</style>
</head>
<body>
<a class="back-link" href="https://billblatzheim.com" style="display:block;padding:10px 24px 0;max-width:1200px;margin:0 auto;">
  <svg width="12" height="10" viewBox="0 0 12 10" fill="none"><path d="M11 5H1M4 1L1 5l3 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  Blatz Labs
</a>
<div class="header">
  <div class="header-inner">
    <div class="top-bar">
      <div style="display:flex;align-items:center;gap:14px;">
        <svg width="36" height="22" viewBox="0 0 36 22"><rect x="0" y="0" width="36" height="7" rx="2" fill="#e8002d"/><rect x="0" y="8" width="36" height="6" rx="2" fill="#fff"/><rect x="0" y="15" width="36" height="7" rx="2" fill="#e8002d"/></svg>
        <span class="logo-text">FORMULA <span>ONE TRACKER</span></span>
      </div>
      <div style="display:flex;align-items:center;gap:16px;">
        <div class="season-btns">
          <span style="font-size:11px;color:#444;letter-spacing:.08em;">SEASON</span>
          {season_btn_html}
        </div>
        <span style="font-size:10px;color:#333;font-family:Barlow,sans-serif;">Updated {generated_at}</span>
      </div>
    </div>
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('standings',this)">STANDINGS</button>
      <button class="tab-btn" onclick="switchTab('races',this)">RACE RESULTS</button>
      <button class="tab-btn" onclick="switchTab('drivers',this)">DRIVER ANALYSIS</button>
    </div>
  </div>
</div>

<div class="body">
  <div id="tab-standings" class="tab-content active"></div>
  <div id="tab-races" class="tab-content"></div>
  <div id="tab-drivers" class="tab-content"></div>
</div>

<script>
const seasonsData = {{}};
{js_data_blocks}

const TEAM_COLORS = {json.dumps(TEAM_COLORS)};
const DRIVER_COLORS = {json.dumps(DRIVER_COLORS)};
const FLAG_MAP = {json.dumps(FLAG_MAP)};

function tc(id){{ return TEAM_COLORS[id]||'#aaa'; }}
function flag(c){{ return FLAG_MAP[c]||'🏁'; }}
function posColor(p){{ return p==='1'?'#FFD700':p==='2'?'#C0C0C0':p==='3'?'#CD7F32':'#555'; }}
function pill(t){{ return `<span class="pill">${{t}}</span>`; }}

let currentSeason = {default_season};
let currentSubTab = 'drivers';
let selectedRound = null;

function switchSeason(s){{
  currentSeason=s; selectedRound=null;
  document.querySelectorAll('.season-btn').forEach(b=>b.classList.toggle('active',parseInt(b.textContent)===s));
  renderAll();
}}
function switchTab(name,el){{
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  if(el) el.classList.add('active');
  renderAll();
}}
function switchSubTab(n){{ currentSubTab=n; renderStandings(); }}
function selectRace(round){{ selectedRound=round; renderRaces(); }}

// ── STANDINGS ─────────────────────────────────────────────────────────────
function renderStandings(){{
  const d=seasonsData[currentSeason]; if(!d) return;
  let bannerHtml='';
  if(d.champion) bannerHtml=`<div class="champ-banner">
    <span style="font-size:28px;">🏆</span>
    <div>
      <div style="font-size:11px;color:#e8002d;font-weight:700;letter-spacing:.1em;">${{currentSeason}} CHAMPIONS</div>
      <div style="font-size:20px;font-weight:900;margin-top:2px;">DRIVERS: ${{d.champion}}</div>
      <div style="font-size:14px;color:#888;margin-top:2px;">CONSTRUCTORS: ${{d.ctor_champion}}</div>
    </div></div>`;

  let subHtml='';
  if(currentSubTab==='drivers'){{
    const st=d.driver_standings||[];
    const maxP=parseFloat(st[0]?.points||1);
    subHtml=st.length===0?'<div class="no-data">No data yet.</div>':st.map((s,i)=>{{
      const color=tc(s.Constructors?.[0]?.constructorId);
      const pct=(parseFloat(s.points)/maxP)*45;
      const rc=i<3?['#FFD700','#C0C0C0','#CD7F32'][i]:'#333';
      return `<div class="standing-row">
        <div style="position:absolute;left:0;top:0;bottom:0;width:${{pct.toFixed(1)}}%;background:${{color}};opacity:.08;border-radius:0 4px 4px 0;"></div>
        <div style="display:flex;align-items:center;gap:18px;position:relative;">
          <span style="width:30px;font-size:18px;font-weight:900;color:${{rc}};text-align:right;flex-shrink:0;">${{s.position}}</span>
          <div style="width:3px;height:36px;background:${{color}};border-radius:2px;flex-shrink:0;"></div>
          <div style="flex:1;">
            <div style="font-size:17px;font-weight:800;">${{s.Driver?.givenName}} <span style="color:${{color}}">${{s.Driver?.familyName?.toUpperCase()}}</span></div>
            <div style="font-size:12px;color:#555;font-family:Barlow,sans-serif;">${{s.Constructors?.[0]?.name}} · ${{s.Driver?.nationality}}</div>
          </div>
          ${{pill(s.wins+' WIN'+(s.wins!=='1'?'S':''))}}
          <div style="text-align:right;"><div style="font-size:24px;font-weight:900;line-height:1;">${{s.points}}</div><div style="font-size:10px;color:#444;letter-spacing:.08em;">PTS</div></div>
        </div></div>`;
    }}).join('');
  }} else {{
    const st=d.constructor_standings||[];
    const maxP=parseFloat(st[0]?.points||1);
    const bw=560,bh=Math.max(200,st.length*36),ih=28;
    const gap=(bh-st.length*ih)/(st.length+1);
    const bars=st.map((s,i)=>{{
      const color=tc(s.Constructor?.constructorId);
      const w=(parseFloat(s.points)/maxP)*(bw-120);
      const y=gap+i*(ih+gap);
      const name=(s.Constructor?.name||'').replace(' F1 Team','').replace(' Racing','');
      return `<text x="110" y="${{(y+ih*.72).toFixed(1)}}" font-size="12" fill="#aaa" text-anchor="end" font-family="Barlow Condensed,sans-serif">${{name}}</text>
        <rect x="118" y="${{y.toFixed(1)}}" width="${{w.toFixed(1)}}" height="${{ih}}" rx="3" fill="${{color}}" opacity=".85"/>
        <text x="${{(118+w+6).toFixed(1)}}" y="${{(y+ih*.72).toFixed(1)}}" font-size="11" fill="#888" font-family="Barlow Condensed,sans-serif">${{s.points}}</text>`;
    }}).join('');
    const rows=st.map((s,i)=>{{
      const color=tc(s.Constructor?.constructorId);
      const pct=(parseFloat(s.points)/maxP)*85;
      const rc=i<3?['#FFD700','#C0C0C0','#CD7F32'][i]:'#333';
      return `<div style="display:flex;align-items:center;gap:18px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:6px;padding:14px 20px;margin-bottom:4px;position:relative;overflow:hidden;">
        <div style="position:absolute;left:0;top:0;bottom:0;width:${{pct.toFixed(1)}}%;background:${{color}};opacity:.07;border-radius:0 4px 4px 0;"></div>
        <span style="width:30px;font-size:18px;font-weight:900;color:${{rc}};text-align:right;position:relative;">${{s.position}}</span>
        <div style="width:3px;height:32px;background:${{color}};border-radius:2px;position:relative;"></div>
        <div style="flex:1;position:relative;"><div style="font-size:16px;font-weight:800;">${{s.Constructor?.name}}</div><div style="font-size:11px;color:#555;font-family:Barlow,sans-serif;">${{s.Constructor?.nationality}}</div></div>
        ${{pill(s.wins+' WIN'+(s.wins!=='1'?'S':''))}}
        <div style="text-align:right;position:relative;"><div style="font-size:24px;font-weight:900;line-height:1;">${{s.points}}</div><div style="font-size:10px;color:#444;letter-spacing:.08em;">PTS</div></div>
      </div>`;
    }}).join('');
    subHtml=st.length===0?'<div class="no-data">No data yet.</div>'
      :`<div class="card" style="padding:24px;margin-bottom:16px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:.1em;color:#555;margin-bottom:16px;">CONSTRUCTOR POINTS</div>
          <svg width="100%" viewBox="0 0 ${{bw}} ${{bh}}" xmlns="http://www.w3.org/2000/svg">${{bars}}</svg>
        </div>${{rows}}`;
  }}

  document.getElementById('tab-standings').innerHTML=`<div class="fade">${{bannerHtml}}
    <div class="sub-btns">
      <button class="sub-btn ${{currentSubTab==='drivers'?'active':''}}" onclick="switchSubTab('drivers')">DRIVERS</button>
      <button class="sub-btn ${{currentSubTab==='constructors'?'active':''}}" onclick="switchSubTab('constructors')">CONSTRUCTORS</button>
    </div>${{subHtml}}</div>`;
}}

// ── RACES ─────────────────────────────────────────────────────────────────
function renderRaces(){{
  const d=seasonsData[currentSeason]; if(!d) return;
  const races=d.races||[];
  if(!selectedRound && races.length>0) selectedRound=races[races.length-1].round;

  const sidebar=races.map(r=>{{
    const country=r.Circuit?.Location?.country||'';
    const short=r.raceName.replace(' Grand Prix','').replace('Grand Prix','').trim();
    const sel=r.round===selectedRound;
    const hasSprint=r.sprint_results && r.sprint_results.length>0;
    return `<div class="race-item${{sel?' selected':''}}" onclick="selectRace('${{r.round}}')">
      <span style="font-size:18px;flex-shrink:0;">${{flag(country)}}</span>
      <div style="flex:1;min-width:0;">
        <div style="font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${{short}}${{hasSprint?' <span style="font-size:9px;background:#FF8000;color:#000;padding:1px 5px;border-radius:3px;font-weight:900;letter-spacing:.05em;vertical-align:middle;">SPRINT</span>':''}}</div>
        <div style="font-size:11px;color:#555;margin-top:1px;">${{r.date}}</div>
      </div>
      <span style="font-size:11px;color:#333;font-weight:700;">R${{r.round}}</span>
    </div>`;
  }}).join('');

  const race=races.find(r=>r.round===selectedRound);
  let detailHtml='<div class="no-data">Select a race from the calendar.</div>';

  if(race){{
    const winnerCtorId=(d.driver_standings||[]).find(s=>s.Driver?.code===race.winner)?.Constructors?.[0]?.constructorId||'';
    const winnerColor=tc(winnerCtorId);
    const hasResults=race.results && race.results.length>0;

    // Podium
    let podiumHtml='';
    if(hasResults && race.results.length>=3){{
      const [p1,p2,p3]=[race.results[0],race.results[1],race.results[2]];
      const pCard=(r,medal,bump)=>{{
        const c=tc(r.Constructor?.constructorId);
        return `<div style="background:rgba(255,255,255,.02);border:1px solid ${{medal==='🥇'?'rgba(255,215,0,.2)':'rgba(255,255,255,.07)'}};border-radius:8px;padding:18px;text-align:center;transform:${{bump?'translateY(-10px)':'none'}};">
          <div style="font-size:26px;margin-bottom:8px;">${{medal}}</div>
          <div style="font-size:20px;font-weight:900;color:${{c}};letter-spacing:.06em;">${{r.Driver?.code||r.Driver?.familyName}}</div>
          <div style="font-size:11px;color:#555;margin-top:3px;font-family:Barlow,sans-serif;">${{r.Constructor?.name}}</div>
          <div style="font-size:22px;font-weight:900;margin-top:10px;">${{r.points}} <span style="font-size:10px;color:#444;">PTS</span></div>
        </div>`;
      }};
      podiumHtml=`<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px;">
        ${{pCard(p2,'🥈',false)}}${{pCard(p1,'🥇',true)}}${{pCard(p3,'🥉',false)}}
      </div>`;
    }}

    // Full results table
    let tableHtml='';
    if(hasResults){{
      const rows=race.results.map(r=>{{
        const c=tc(r.Constructor?.constructorId);
        const fin=r.status==='Finished'||r.status?.includes('Lap');
        const fl=r.FastestLap?.rank==='1';
        const gained=r.grid&&r.position?parseInt(r.grid)-parseInt(r.position):null;
        const gainedStr=gained===null?'—':gained>0?`<span style="color:#4ade80;">▲${{gained}}</span>`:gained<0?`<span style="color:#f87171;">▼${{Math.abs(gained)}}</span>`:'<span style="color:#555;">—</span>';
        return `<div class="results-row">
          <span style="font-weight:900;font-size:16px;color:${{posColor(r.position)}}">${{r.position}}</span>
          <span style="font-size:10px;text-align:center;color:#444;">${{r.grid||'—'}}</span>
          <div><span style="font-weight:600;font-size:14px;">${{r.Driver?.givenName?.charAt(0)}}. </span><span style="font-weight:900;font-size:14px;color:${{c}}">${{r.Driver?.familyName}}</span>${{fl?' <span style="font-size:10px;color:#FF8000;margin-left:4px;">⚡FL</span>':''}}</div>
          <span style="font-size:12px;color:#555;font-family:Barlow,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${{r.Constructor?.name}}</span>
          <span style="font-size:11px;color:${{fin?'#4ade80':'#f87171'}};font-family:Barlow,sans-serif;">${{r.status}}</span>
          <span style="font-size:12px;color:#555;text-align:center;">${{r.laps}}</span>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;">
            <span style="font-size:14px;font-weight:700;color:${{r.points!=='0'?'#FFD700':'#444'}}">${{r.points}}</span>
            <span style="font-size:10px;">${{gainedStr}}</span>
          </div>
        </div>`;
      }}).join('');
      tableHtml=`<div class="card" style="overflow:hidden;">
        <div class="results-hdr"><span>FIN</span><span style="color:#444;font-size:9px;">GRD</span><span>DRIVER</span><span>TEAM</span><span>STATUS</span><span style="text-align:center;">LAPS</span><span style="text-align:right;">PTS ±POS</span></div>
        ${{rows}}
      </div>`;
    }} else {{
      tableHtml=`<div class="card" style="padding:20px;">
        <div style="font-size:13px;color:#555;font-family:Barlow,sans-serif;">
          Full results not loaded. Run: <code style="color:#e8002d;">python3 f1_dashboard_multi.py --add ${{currentSeason}}</code>
        </div>
      </div>`;
    }}

    // Sprint results
    let sprintHtml='';
    const hasSprint=race.sprint_results && race.sprint_results.length>0;
    if(hasSprint){{
      const sprintWinner=race.sprint_results[0];
      const swc=tc(sprintWinner.Constructor?.constructorId);
      const sprintRows=race.sprint_results.map(r=>{{
        const c=tc(r.Constructor?.constructorId);
        const fin=r.status==='Finished'||r.status?.includes('Lap');
        return `<div class="results-row">
          <span style="font-weight:900;font-size:16px;color:${{posColor(r.position)}}">${{r.position}}</span>
          <span style="font-size:10px;text-align:center;color:#444;">${{r.grid||'—'}}</span>
          <div><span style="font-weight:600;font-size:14px;">${{r.Driver?.givenName?.charAt(0)}}. </span><span style="font-weight:900;font-size:14px;color:${{c}}">${{r.Driver?.familyName}}</span></div>
          <span style="font-size:12px;color:#555;font-family:Barlow,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${{r.Constructor?.name}}</span>
          <span style="font-size:11px;color:${{fin?'#4ade80':'#f87171'}};font-family:Barlow,sans-serif;">${{r.status}}</span>
          <span style="font-size:12px;color:#555;text-align:center;">${{r.laps}}</span>
          <div style="text-align:right;"><span style="font-size:14px;font-weight:700;color:${{r.points!=='0'?'#FFD700':'#444'}}">${{r.points}}</span></div>
        </div>`;
      }}).join('');
      sprintHtml=`<div style="margin-bottom:20px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
          <span style="background:#FF8000;color:#000;font-size:10px;font-weight:900;padding:3px 10px;border-radius:4px;letter-spacing:.1em;">⚡ SPRINT RACE</span>
          <span style="font-size:13px;color:#888;font-family:Barlow,sans-serif;">Winner: <span style="color:${{swc}};font-weight:700;">${{sprintWinner.Driver?.givenName}} ${{sprintWinner.Driver?.familyName}}</span></span>
        </div>
        <div class="card" style="overflow:hidden;">
          <div class="results-hdr"><span>FIN</span><span style="color:#444;font-size:9px;">GRD</span><span>DRIVER</span><span>TEAM</span><span>STATUS</span><span style="text-align:center;">LAPS</span><span style="text-align:right;">PTS</span></div>
          ${{sprintRows}}
        </div>
      </div>`;
    }}

    detailHtml=`
      <div style="margin-bottom:20px;">
        <div style="font-size:11px;color:#e8002d;letter-spacing:.12em;font-weight:700;margin-bottom:6px;">ROUND ${{race.round}} · ${{(race.Circuit?.Location?.country||'').toUpperCase()}}</div>
        <div style="font-size:30px;font-weight:900;letter-spacing:.05em;line-height:1;">${{race.raceName.toUpperCase()}}</div>
        <div style="font-size:13px;color:#555;margin-top:6px;font-family:Barlow,sans-serif;">${{race.Circuit?.circuitName}} · ${{race.date}}</div>
      </div>
      ${{sprintHtml}}${{podiumHtml}}${{tableHtml}}`;
  }}

  const sprintCount=races.filter(r=>r.sprint_results&&r.sprint_results.length>0).length;
  const sprintLabel=sprintCount>0?` · ${{sprintCount}} ⚡ SPRINTS`:'';
  document.getElementById('tab-races').innerHTML=`<div class="fade race-grid">
    <div class="card race-sidebar">
      <div style="padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.06);font-size:11px;font-weight:700;letter-spacing:.1em;color:#555;">${{currentSeason}} CALENDAR · ${{races.length}} RACES${{sprintLabel}}</div>
      <div class="race-list">${{sidebar||'<div class="no-data">No races yet.</div>'}}</div>
    </div>
    <div>${{detailHtml}}</div>
  </div>`;
}}

// ── DRIVERS ───────────────────────────────────────────────────────────────
function renderDrivers(){{
  const d=seasonsData[currentSeason]; if(!d) return;
  const prog=d.progression||{{}};
  const labels=d.race_labels||[];
  const codes=Object.keys(prog).slice(0,8);
  const standings=d.driver_standings||[];

  const CW=820,CH=300,PL=45,PR=20,PT=10,PB=44;
  const n=labels.length;
  const allPts=codes.flatMap(c=>prog[c]||[]).filter(Number.isFinite);
  const yMax=allPts.length?Math.max(...allPts)*1.05:500;
  const cx=i=>PL+(i/Math.max(n-1,1))*(CW-PL-PR);
  const cy=v=>PT+CH-PB-(v/yMax)*(CH-PT-PB);

  // Build a single color map keyed by driver code so chart, legend, and table all match
  const colorMap={{}};
  codes.forEach((code,di)=>{{ colorMap[code]=DRIVER_COLORS[di%DRIVER_COLORS.length]; }});

  let lines='';
  codes.forEach((code)=>{{
    const color=colorMap[code];
    const pts=(prog[code]||[]).filter((_,i)=>i<n);
    if(pts.length<2) return;
    const coords=pts.map((v,i)=>[cx(i),cy(v)]);
    const da=`M ${{coords[0][0].toFixed(1)}},${{coords[0][1].toFixed(1)}} `+coords.slice(1).map(([x,y])=>`L ${{x.toFixed(1)}},${{y.toFixed(1)}}`).join(' ');
    const [lx,ly]=coords[coords.length-1];
    lines+=`<path d="${{da}}" stroke="${{color}}" stroke-width="2" fill="none" opacity=".9"/>
      <circle cx="${{lx.toFixed(1)}}" cy="${{ly.toFixed(1)}}" r="4" fill="${{color}}"/>
      <text x="${{(lx+6).toFixed(1)}}" y="${{(ly+4).toFixed(1)}}" fill="${{color}}" font-size="10" font-family="Barlow Condensed,sans-serif">${{code}}</text>`;
  }});

  let axes='';
  for(let v=0;v<=yMax;v+=50){{
    const y=cy(v);
    axes+=`<line x1="${{PL}}" y1="${{y.toFixed(1)}}" x2="${{CW-PR}}" y2="${{y.toFixed(1)}}" stroke="#1a1a2a" stroke-width="1"/>
      <text x="${{PL-6}}" y="${{(y+4).toFixed(1)}}" fill="#444" font-size="10" text-anchor="end" font-family="Barlow Condensed,sans-serif">${{v}}</text>`;
  }}
  labels.forEach((lbl,i)=>{{
    if(i%3===0) axes+=`<text x="${{cx(i).toFixed(1)}}" y="${{CH-PB+14}}" fill="#444" font-size="9" text-anchor="middle" font-family="Barlow Condensed,sans-serif">${{lbl}}</text>`;
  }});

  const legend=codes.map((code)=>{{
    const color=colorMap[code];
    return `<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:12px;color:${{color}};">
      <span style="display:inline-block;width:20px;height:2px;background:${{color}};border-radius:2px;"></span>${{code}}</span>`;
  }}).join('');

  // Stats — use race results if available, else standings
  const statMap={{}};
  (d.races||[]).forEach(race=>{{
    (race.results||[]).forEach(r=>{{
      const code=r.Driver?.code||r.Driver?.familyName?.slice(0,3).toUpperCase()||'';
      if(!statMap[code]) statMap[code]={{wins:0,podiums:0,dnfs:0,pts:0}};
      if(r.position==='1') statMap[code].wins++;
      if(['1','2','3'].includes(r.position)) statMap[code].podiums++;
      const st=r.status||'';
      if(st&&st!=='Finished'&&!st.includes('Lap')) statMap[code].dnfs++;
      statMap[code].pts+=parseFloat(r.points||0);
    }});
  }});

  const useStandings=Object.keys(statMap).length===0;
  const topDrivers=useStandings
    ?standings.slice(0,15).map(s=>[s.Driver?.code||'',({{wins:parseInt(s.wins||0),podiums:'–',dnfs:'–',pts:parseFloat(s.points||0)}})])
    :Object.entries(statMap).sort((a,b)=>b[1].pts-a[1].pts).slice(0,15);

  const statRows=topDrivers.map(([code,st])=>{{
    // Use the shared colorMap if this driver is in the chart, otherwise assign a grey
    const color=colorMap[code]||'#888';
    const fd=(standings.find(s=>s.Driver?.code===code)||{{}}).Driver;
    const name=fd?`${{fd.givenName}} ${{fd.familyName}}`:code;
    return `<div style="display:grid;grid-template-columns:1fr 80px 100px 80px 100px;padding:12px 20px;border-bottom:1px solid rgba(255,255,255,.03);align-items:center;">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:3px;height:26px;background:${{color}};border-radius:2px;flex-shrink:0;"></div>
        <div><div style="font-size:16px;font-weight:800;color:${{color}};letter-spacing:.04em;">${{code}}</div><div style="font-size:11px;color:#555;font-family:Barlow,sans-serif;">${{name}}</div></div>
      </div>
      <div style="text-align:center;font-size:22px;font-weight:900;color:#FFD700;">${{st.wins}}</div>
      <div style="text-align:center;font-size:22px;font-weight:900;color:#C0C0C0;">${{st.podiums}}</div>
      <div style="text-align:center;font-size:22px;font-weight:900;color:#f87171;">${{st.dnfs}}</div>
      <div style="text-align:right;"><span style="font-size:22px;font-weight:900;">${{Math.round(st.pts)}}</span><span style="font-size:10px;color:#444;margin-left:4px;">PTS</span></div>
    </div>`;
  }}).join('');

  document.getElementById('tab-drivers').innerHTML=`<div class="fade">
    <div class="card" style="padding:28px;margin-bottom:20px;">
      <div style="font-size:11px;font-weight:700;letter-spacing:.1em;color:#555;margin-bottom:4px;">CUMULATIVE CHAMPIONSHIP POINTS — ${{currentSeason}}</div>
      <div style="font-size:11px;color:#444;font-family:Barlow,sans-serif;margin-bottom:20px;">Top 8 drivers</div>
      ${{codes.length===0?'<div class="no-data">No progression data yet.</div>'
        :`<svg width="100%" viewBox="0 0 ${{CW}} ${{CH}}" xmlns="http://www.w3.org/2000/svg" style="overflow:visible">${{axes}}${{lines}}</svg>
          <div style="margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,.06);">${{legend}}</div>`}}
    </div>
    <div class="card" style="overflow:hidden;">
      <div style="padding:12px 20px;border-bottom:1px solid rgba(255,255,255,.06);font-size:11px;font-weight:700;letter-spacing:.1em;color:#555;">WINS · PODIUMS · DNFs — ${{currentSeason}}</div>
      <div style="display:grid;grid-template-columns:1fr 80px 100px 80px 100px;padding:10px 20px;border-bottom:1px solid rgba(255,255,255,.06);font-size:10px;font-weight:700;letter-spacing:.1em;color:#444;">
        <span>DRIVER</span><span style="text-align:center">WINS</span><span style="text-align:center">PODIUMS</span><span style="text-align:center">DNFs</span><span style="text-align:right">POINTS</span>
      </div>
      ${{statRows||'<div class="no-data">No data yet.</div>'}}
    </div>
  </div>`;
}}

function renderAll(){{
  const active=document.querySelector('.tab-content.active')?.id?.replace('tab-','');
  if(!active||active==='standings') renderStandings();
  else if(active==='races') renderRaces();
  else if(active==='drivers') renderDrivers();
}}

renderAll();
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def parse_year_args(flag):
    """Return list of integer years following a flag like --add or --refresh."""
    years = []
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        for arg in sys.argv[idx+1:]:
            if arg.startswith('--'):
                break
            try:
                years.append(int(arg))
            except ValueError:
                pass
    return years

def main():
    add_seasons     = parse_year_args('--add')
    refresh_seasons = parse_year_args('--refresh')
    fetch_needed    = list(dict.fromkeys(add_seasons + refresh_seasons))  # deduped, order preserved

    print("\n🏎️  F1 Multi-Season Dashboard Generator")

    # Load cache
    cache = load_cache()
    if cache:
        print(f"  📂 Cache loaded — seasons: {sorted(cache.keys(), reverse=True)}")
    else:
        print("  📂 No cache found — run --add to fetch full race results")

    # Start with baked-in data, then overlay cache, so cache always wins
    all_data = dict(SEASONS_DATA)
    all_data.update(cache)

    # Fetch any requested seasons
    if fetch_needed:
        if not HAS_REQUESTS:
            print("  ⚠️  'requests' not installed. Run: python3 -m pip install requests")
            sys.exit(1)
        cache_dirty = False
        for season in fetch_needed:
            if season in cache and season not in refresh_seasons:
                print(f"\n  ⏭️  {season} already cached — skipping (use --refresh {season} to force)")
                continue
            print(f"\n📡 Fetching full results for {season}...")
            try:
                data = fetch_season(season)
                all_data[season] = data
                cache[season] = data
                cache_dirty = True
                print(f"  ✅ {season} complete — {len(data['races'])} races fetched")
            except Exception as e:
                print(f"  ❌ Failed to fetch {season}: {e}")
                print(f"     Using cached/baked-in data if available.")
        if cache_dirty:
            save_cache(cache)

    print(f"\n📦 Seasons: {sorted(all_data.keys(), reverse=True)}")
    print("🎨 Generating HTML...")

    generated_at = datetime.now().strftime("%b %d, %Y")
    html = generate_html(all_data, generated_at)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = len(html.encode()) / 1024
    print(f"✅ Done! → index.html  ({size_kb:.0f} KB)\n")
    print("Tips:")
    print("  python3 f1_dashboard_multi.py                        # rebuild from cache")
    print("  python3 f1_dashboard_multi.py --add 2026             # fetch & cache 2026")
    print("  python3 f1_dashboard_multi.py --refresh 2025         # re-fetch 2025\n")

if __name__ == "__main__":
    main()
