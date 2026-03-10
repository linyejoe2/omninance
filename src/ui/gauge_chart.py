from pyecharts.commons.utils import JsCode

from indicators import BaseIndicator as Ba



def render_gauge_chart(ind: Ba):
    bg_color = "transparent"
    text_color = "#333"

    min_v = float(ind.min_val)
    max_v = float(ind.max_val)

    js_formatter = JsCode(
        f"function(value) {{"
        f"  var p = Math.round((value - {min_v}) / ({max_v} - {min_v}) * 100);"
        f"  var targets = [0, 30, 50, 70, 100];"
        f"  if (targets.indexOf(p) !== -1) return value;"
        f"  return '';"
        f"}}"
    )

    if ind.score >= 1:
        text_color = "#008046"
        if ind.score >= 2:
            bg_color = "#00ba67"
            text_color = "#ffffff"
    elif ind.score <= -1:
        text_color = "#b91d1d"
        if ind.score <= -2:
            bg_color = "#ff4b4b"
            text_color = "#ffffff"

    return {
        "series": [{
            "type": 'gauge',
            "startAngle": 210,
            "endAngle": -30,
            "min": round(float(ind.min_val), 2),
            "max": round(float(ind.max_val), 2),
            "splitNumber": 4,
            "radius": '100%',
            "axisLine": {
                "distance": -15,
                "lineStyle": {
                    "width": 15,
                    "color": [[0.3, '#67e0e3'], [0.7, '#fac858'], [1, '#fd666d']]
                }
            },
            "splitLine": {
                "distance": -15,
                "length": 15,
                "lineStyle": {
                    "color": '#fff',
                    "width": 4
                }
            },
            "axisTick": {
                "distance": -15,
                "length": 8,
                "lineStyle": {
                    "color": '#fff',
                    "width": 2
                }
            },
            "axisLabel": {
                "distance": 10,
                "color": '#fff',
                "fontSize": 14,
                "show": True
            },
            "pointer": {"width": 3, "length": '60%'},
            "title": {
                "offsetCenter": [0, '85%'],
                "fontSize": 24,
                "color": "#fff",
                "show": True
            },
            "detail": {
                "offsetCenter": [0, '60%'],
                "valueAnimation": True,
                "formatter": "{style|{value}}",
                "rich": {
                    "style": {
                        "fontSize": 18,
                        "fontWeight": 'bold',
                        "color": text_color,
                        "backgroundColor": bg_color,
                        "padding": [2, 6],
                        "borderRadius": 4
                    }
                }
            },
            "data": [{"value": round(float(ind.current_value), 2), "name": ind.name}]
        }]
    }
