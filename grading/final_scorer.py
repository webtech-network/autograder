from grading.grader import grade
from utils.path import Path

def get_final_score(html_weight,css_weight,js_weight):
    path = Path(__file__,'tests')
    html_score = grade(path.getFilePath('test_html.py'),24)
    css_score = grade(path.getFilePath('test_css.py'),11)
    js_score = grade(path.getFilePath('test_js.py'),15)
    final_score = (
        ((html_score * html_weight))+
        ((css_score * css_weight)) + 
        ((js_score * js_weight)))/100
    return final_score

def test_path(weight):
    return f"Weight is {weight}"


