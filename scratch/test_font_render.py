from weasyprint import HTML
from PIL import Image
from io import BytesIO

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page { size: 800px 400px; margin: 0; }
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: #f4f6f7;
    margin: 0;
    padding: 20px;
}
.title {
    font-size: 24px;
    font-weight: bold;
    color: #1a1a1a;
}
.sub {
    font-size: 14px;
    color: #475569;
}
.team {
    font-size: 16px;
    font-weight: 600;
    color: #2c3e50;
}
</style>
</head>
<body>
<div class="title">TOP 20 COLOMBIA</div>
<div class="sub">22/09/2026 18:33 Hora de Colombia</div>
<div class="team">1. UTP - CodeDeGrace 11 (1462)</div>
<div class="team">2. UN ALL IN 10 (967)</div>
<div class="team">3. SQLazo &#x1F911; (1125)</div>
<div class="team">19. UNIVALLE EN RPC &#x1F60E;&#x1F4C8;top1</div>
<div class="sub">UNIVALLE EN NACIONAL &#x1F921;&#x1F4C9;top100</div>
</body>
</html>
"""

png_bytes = HTML(string=html).write_png()
with open("/workspace/scratch/test_font_render.png", "wb") as f:
    f.write(png_bytes)
print("Saved /workspace/scratch/test_font_render.png successfully!")
