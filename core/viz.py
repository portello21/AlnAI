import plotly.express as px
import pandas as pd

def generate_financial_chart(data: dict):
    df = pd.DataFrame(data)
    fig = px.line(df, x='mes', y='valor', title="Projeção Financeira CAD 5.000")
    return fig