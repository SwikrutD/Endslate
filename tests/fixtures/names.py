"""Real filenames from a real library, with the parse each one must produce.

This file is the parser's specification. Add a row whenever a name surprises you.
"""

# (name, is_dir, expected subset of the parse)
MOVIE_NAMES = [
    ("Fight.Club.1999.REMASTERED.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv", False,
     {"title": "Fight Club", "year": 1999, "edition": "Remastered"}),
    ("American Psycho 2000 2160p 10bit BluRay HEVC [English DTS-HD.MA 7.1 + English TrueHD.Atmos 7.1 + English DD 5.1] H.265 SWTYBLZ-4kHdHub.com.mkv", False,
     {"title": "American Psycho", "year": 2000}),
    ("6.Underground.2019.2160p.4K.WEB.x265.10bit.AAC5.1-[YTS.MX].mkv", False,
     {"title": "6 Underground", "year": 2019}),
    ("Angry.Birds.Movie.2016.720p.WEBRip.750MB.MkvCage.mkv", False,
     {"title": "Angry Birds Movie", "year": 2016}),
    ("Dune - Part One (2021) 1080p BluRay 10bit HEVC [Hindi DDP 5.1   English DDP 7.1] x265 (DarQ-LUMiX) 4KHDHub.com.mkv", False,
     {"title": "Dune - Part One", "year": 2021}),
    ("Zoolander.2.2016.720p.BluRay.x264-ESub.Hollymoviehd.mkv", False,
     {"title": "Zoolander 2", "year": 2016}),
    ("Housefull 5A (2025) Bollywood Hindi Movie PreDvD 1080p.mkv", False,
     {"title": "Housefull 5", "year": 2025, "part": "A"}),
    ("Mr. and Mrs. Smith 2005 [Directors Cut] 1080p 10bit BluRay HEVC x265 [Hindi JC DDP 2.0 224kbps + Englsh DD 5.1] ESub-xtrem3x-TAoE-4kHdHub.mkv", False,
     {"title": "Mr. and Mrs. Smith", "year": 2005, "edition": "Directors Cut"}),
    ("Tropic Thunder (2008) [UNRATED DC] [REPACK] [1080p] [BluRay] [5.1] [YTS.MX]", True,
     {"title": "Tropic Thunder", "year": 2008, "edition": "Unrated Directors Cut"}),
    ("The.Hangover.Part.II.2011.1080p.BluRay.x264.AAC5.1-[YTS.MX].mp4", False,
     {"title": "The Hangover Part II", "year": 2011}),
    ("Demon.Slayer.Kimetsu.No.Yaiba.Infinity.Castle.2025.1080p", True,
     {"title": "Demon Slayer Kimetsu No Yaiba Infinity Castle", "year": 2025}),
    ("Project Hail Mary (2026) [IMAX] 1080p iTunes WEBRip HEVC x265 [Hindi AMZN DDP 5.1 640kbps + English AAC 5.1] ESub-(PSA-4kHdHub)", True,
     {"title": "Project Hail Mary", "year": 2026, "edition": "IMAX"}),
    ("WALL-E (2008) [1080p]", True, {"title": "WALL-E", "year": 2008}),
    ("IT (2017)", True, {"title": "IT", "year": 2017}),
    ("My Big Fat Greek Wedding 2 2016", True, {"title": "My Big Fat Greek Wedding 2", "year": 2016}),
    ("The Lego Movie (2014)", True, {"title": "The Lego Movie", "year": 2014}),
    ("The English Patient 1996 1080p BluRay", True, {"title": "The English Patient", "year": 1996}),
    ("Ghost in the Shell (2017) 1080p 10bit BluRay HEVC x265 [Hindi-Tamil-Telugu AMZN DDP 2.0 224kbps + English DD-EX 5.1] ESub-(MNHD-FRDS-4kHdHub)", True,
     {"title": "Ghost in the Shell", "year": 2017}),
    ("Sitaare Zameen Par (2025) 1080p x264 [Hnidi+Tam+Tel]", True, {"title": "Sitaare Zameen Par", "year": 2025}),
    ("Spirited.Away.2001.1080p.NF.WEB-DL.Multi.AAC5.1.AV1-4kHdHub.Com", True, {"title": "Spirited Away", "year": 2001}),
    ("Thor 2 - The Dark World", True, {"title": "Thor 2 - The Dark World", "year": None}),
    ("Rush Hour", True, {"title": "Rush Hour", "year": None}),
    ("Beauty And The Beast", True, {"title": "Beauty And The Beast", "year": None}),
    ("INDIANA JONES RAIDERS LOST ARK", True, {"title": "Indiana Jones Raiders Lost Ark"}),
]

EPISODE_NAMES = [
    ("The.100.S01E04.Murphys.Law.1080p.AMZN.WEB-DL.English.DDP5.1.H.265-4kHdHub.Com.mkv", False,
     {"title": "The 100", "season": 1, "episode": 4, "episode_title": "Murphys Law"}),
    ("ONE.PIECE.S01E01.ROMANCE.DAWN.1080p.NF.WEB-DL.Multi.AAC5.1.AV1-4kHdHub.Com.mkv", False,
     {"title": "One Piece", "season": 1, "episode": 1, "episode_title": "Romance Dawn"}),
    ("Dark.S02E03.Ghosts.1080p.NF.WEB-DL.English.DDP5.1-German.DDP5.1.H.265-4kHdHub.Com.mkv", False,
     {"title": "Dark", "season": 2, "episode": 3, "episode_title": "Ghosts"}),
    ("Modern Family (2009) - S01E01 - Pilot (1080p BluRay x265 Silence).mkv", False,
     {"title": "Modern Family", "year": 2009, "season": 1, "episode": 1, "episode_title": "Pilot"}),
    ("Gravity Falls - 1x18 - Land Before Swine.eng.srt", False,
     {"title": "Gravity Falls", "season": 1, "episode": 18, "episode_title": "Land Before Swine"}),
    ("Squid.Game.S03E04.222.1080p.NF.WEB-DL.Multi.AAC5.1.AV1-4kHdHub.Com.mkv", False,
     {"title": "Squid Game", "season": 3, "episode": 4, "episode_title": "222"}),
    ("Game of Thrones (2011) S01E02 1080p BluRay 10bit HEVC [Hindi-Tamil-Telugu-Kannada DDP 2.0 + English TrueHD Atmos 7.1] x265 [Absinth-4kHDHUB.Com].mkv", False,
     {"title": "Game of Thrones", "year": 2011, "season": 1, "episode": 2}),
    ("Dark - 1x02 - Lugen.WEB.STRiFE.en.srt", False,
     {"title": "Dark", "season": 1, "episode": 2, "language": "en"}),
    ("The.100.S05.1080p.AMZN.WEB-DL.English.DDP5.1.H.265-4kHdHub", True,
     {"title": "The 100", "season": 5}),
    ("Season 10 (AMZN WEB-DL)", True, {"season": 10}),
    ("Dark - season 1.en", True, {"title": "Dark", "season": 1}),
]

SUBTITLE_NAMES = [
    ("dan.srt", "da"),
    ("pol.srt", "pl"),
    ("Latin American.spa.srt", "es"),
    ("Brazilian.por.srt", "pt"),
    ("English.srt", "en"),
    ("Forced.eng.srt", "en"),
    ("The.Hangover.Part.Ii.English-WWW.MY-SUBS.NET.srt", "en"),
    ("Gravity Falls - 1x18 - Land Before Swine.eng.srt", "en"),
]

JUNK_NAMES = [
    "._Black Panther 2018 1080p.mp4",
    ".DS_Store",
    "desktop.ini",
    "Thumbs.db",
    "www.YTS.MX.jpg",
    "YIFYStatus.com.txt",
    "YTSProxies.com.txt",
    "WWW.YIFY-TORRENTS.COM.jpg",
    "Torrent Downloaded From ExtraTorrent.com.txt",
    "AhaShare.com.txt",
    "YTSYifyUP... (TOR).txt",
    "jquery.min.js",
    "en-auto.m3u8",
]

KEEP_NAMES = [
    "poster.jpg",
    "folder.jpg",
    "fanart.jpg",
    "Fight Club (1999).mkv",
    "Fight Club (1999).en.srt",
]
