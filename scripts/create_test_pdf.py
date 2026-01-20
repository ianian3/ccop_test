#!/usr/bin/env python3
"""테스트용 법률 PDF 생성"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
import os

# 한글 폰트 등록 (macOS 기본 폰트)
font_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('AppleGothic', font_path))
    font_name = 'AppleGothic'
else:
    font_name = 'Helvetica'

def create_test_pdf(filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    # 제목
    c.setFont(font_name, 18)
    c.drawString(2*cm, height - 2*cm, "형법 및 특별법 - 테스트 문서")
    
    # 내용
    c.setFont(font_name, 12)
    y = height - 4*cm
    
    content = [
        "제347조 (사기)",
        "1. 사람을 기망하여 재물의 교부를 받거나 재산상의 이익을 취득한 자는",
        "   10년 이하의 징역 또는 2천만원 이하의 벌금에 처한다.",
        "",
        "제348조 (준사기)",
        "미성년자의 지려천박 또는 사람의 심신장애를 이용하여 재물의 교부를",
        "받거나 재산상의 이익을 취득한 자는 10년 이하의 징역 또는",
        "2천만원 이하의 벌금에 처한다.",
        "",
        "전기통신금융사기 피해 방지 및 피해금 환급에 관한 특별법",
        "",
        "제15조 (벌칙)",
        "1. 사기행위에 이용될 것을 알면서 전기통신금융사기에 사용된 타인 명의의",
        "   접근매체를 점유, 사용한 자는 3년 이하의 징역 또는",
        "   3천만원 이하의 벌금에 처한다.",
        "",
        "특정경제범죄 가중처벌 등에 관한 법률",
        "",
        "제3조 (특정재산범죄의 가중처벌)",
        "1. 형법 제347조(사기)의 죄를 범한 자는 그 범죄행위로 인하여",
        "   취득하거나 제3자로 하여금 취득하게 한 재물 또는 재산상 이익의",
        "   가액(이득액)이 5억원 이상인 경우에는 3년 이상의 유기징역에 처한다.",
        "2. 이득액이 50억원 이상인 경우에는 무기 또는 5년 이상의 징역에 처한다.",
        "",
        "보이스피싱 관련 판례 요약",
        "",
        "- 보이스피싱 조직의 대포통장 모집책: 징역 2년 6월",
        "- 보이스피싱 인출책(수거책): 징역 3년",
        "- 보이스피싱 콜센터 운영자: 징역 5년 ~ 10년",
        "",
        "양형 기준:",
        "- 초범인 경우 집행유예 가능성 있음",
        "- 피해 금액에 비례하여 형량 결정",
        "- 피해자 합의 시 감형 가능",
    ]
    
    for line in content:
        if y < 2*cm:
            c.showPage()
            c.setFont(font_name, 12)
            y = height - 2*cm
        c.drawString(2*cm, y, line)
        y -= 0.6*cm
    
    c.save()
    print(f"Created: {filename}")

if __name__ == "__main__":
    create_test_pdf("docs/test_law.pdf")
