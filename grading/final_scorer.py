from grader import grade


def get_final_score(html_weight,css_weight,js_weight):
    html_score = grade('../tests/test_html.py',24)
    css_score = grade('../tests/test_css.py',11)
    js_score = grade('../tests/test_js.py',15)
    final_score = (
        ((html_score * html_weight))+
        ((css_score * css_weight)) + 
        ((js_score * js_weight)))/100
    return final_score

print(get_final_score(30,40,30))

