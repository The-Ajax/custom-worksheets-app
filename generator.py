from openai import OpenAI
import json
import os
import matplotlib.pyplot as plt
import re
from weasyprint import HTML
import secrets

from settings import settings

client = OpenAI(
    api_key=settings.openai_api_key
)

description_f = open("worksheet_templates/description.txt")


def latex_to_svg(latex: str, filename: str):
    fig = plt.figure()
    fig.patch.set_alpha(0.0)
    text_obj = fig.text(0, 0, f"${latex}$", fontsize=16)

    fig.canvas.draw()
    bbox = text_obj.get_window_extent()

    dpi = fig.dpi
    width, height = bbox.width / dpi, bbox.height / dpi
    fig.set_size_inches(width, height)


    fig.savefig(filename, format="svg", bbox_inches='tight', transparent=True)
    plt.close(fig)


def embed_math_as_svg(text: str, base_filename: str) -> str:
    math_pattern = r"\$(.*?)\$"
    matches = re.findall(math_pattern, text)

    for i, expr in enumerate(matches):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        svg_dir = os.path.join(base_dir, "math_svgs")
        os.makedirs(svg_dir, exist_ok=True)

        svg_filename = f"math_{base_filename}_{i}.svg"
        svg_full_path = os.path.join(svg_dir, svg_filename)
        latex_to_svg(expr, svg_full_path)
        
        absolute_path = os.path.abspath(svg_full_path).replace("\\", "/")
        text = text.replace(f"${expr}$", f'<img src="file:///{absolute_path}" alt="{expr}" style="vertical-align: middle;">')

    return text

def create_problem_sheet(subject: str, difficulty: str, num_problems: int, add_info: str = "") -> bool:
    user_prompt = """
        I want {} problems on the subject of {}. The difficulty should be {}.
        Here are some additional information about the problem sheet: {}
        Please give me the result in just JSON format, following the system prompt template(problems and answers).
        The json will be directly processed by a python script, so no '''json and no metadata.
        """.format(num_problems, subject, difficulty, add_info)
    
    response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": description_f.read()},
        {"role": "user", "content": user_prompt}]
    )
    sheet_id = secrets.token_hex(8)

    prob_ans_sheet = str(response.choices[0].message.content.strip())

    with open('response.txt', 'w', encoding='utf-8') as f: # Check GPT-4o response directly
        f.write(prob_ans_sheet)

    prob_ans_sheet_json = json.loads(prob_ans_sheet)

    problems = prob_ans_sheet_json.get("problems", [])
    html_content = """"""

    with open('worksheet_templates/start.html', 'r', encoding='utf-8') as f:
        html_content += f.read()

    for i, item in enumerate(problems, 1):
        problem = embed_math_as_svg(item.get("problem", ""), f"{sheet_id}_problem_{i}")   

        html_content += f"""
        <div class="problem-container">
            <div class="problem-number">Problem {i}</div>
            <div class="problem-text">{problem}</div>
        </div>
        """

    html_content += """
        <div class="answer-section">
            <h2>Answers</h2>
    """

    for i, item in enumerate(problems, 1):
        answer = embed_math_as_svg(item.get("answer", ""), f"{sheet_id}_answer_{i}")

        html_content += f"""
            <div class="answer-container">
                <div class="answer-number">Problem {i}:</div>
                <div>{answer}</div>
            </div>
    """

        
    html_content += """
    </body>
    </html>
    """
    
    with open('worksheet_templates/res.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    return True


def convert_html_to_pdf(html_path: str, pdf_filename: str) -> str | None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_dir = os.path.join(base_dir, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)

    svg_dir = os.path.join(base_dir, "math_svgs")
    
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    try:
        HTML(filename=html_path).write_pdf(pdf_path)

        for filename in os.listdir(svg_dir):
            file_path = os.path.join(svg_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

        return pdf_path
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None