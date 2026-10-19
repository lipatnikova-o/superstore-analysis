import dash
from dash import dcc, html, Input, Output
import pandas as pd
import sqlite3
import plotly.express as px

# ---------- Данные ----------
conn = sqlite3.connect('superstore.db')
df = pd.read_sql('SELECT order_date, region, category, sub_category, order_id, sales, profit, discount FROM superstore', conn)
df['year'] = pd.to_datetime(df['order_date']).dt.year

years = sorted(df['year'].unique())
regions = sorted(df['region'].unique())
categories = sorted(df['category'].unique())

# ---------- Цвета категорий (фиксированные) ----------
CATEGORY_COLORS = {
    'Furniture': '#d62728',        # красный
    'Technology': '#1f77b4',       # синий
    'Office Supplies': '#2ca02c',  # зелёный
}

# ---------- Фильтрация ----------
def filter_df(year=None, region=None, category=None):
    filtered = df.copy()
    if year and year != 'all':
        filtered = filtered[filtered['year'] == int(year)]
    if region and region != 'all':
        filtered = filtered[filtered['region'] == region]
    if category and category != 'all':
        filtered = filtered[filtered['category'] == category]
    return filtered

# ---------- KPI ----------
def calculate_kpi(year=None, region=None, category=None):
    filtered = filter_df(year, region, category)
    if len(filtered) == 0:
        return (0, 0, 0, 0)
    total_sales = filtered['sales'].sum()
    total_profit = filtered['profit'].sum()
    margin = (total_profit / total_sales * 100) if total_sales else 0
    num_orders = filtered['order_id'].nunique()
    return (total_sales, total_profit, margin, num_orders)

# ---------- График динамики ----------
def build_dynamics_chart(year=None, region=None, category=None):
    filtered = filter_df(year, region, category)
    grouped = filtered.groupby('year').agg(
        total_sales=('sales', 'sum'),
        total_profit=('profit', 'sum')
    ).reset_index()

    fig = px.line(
        grouped, x='year', y=['total_sales', 'total_profit'],
        markers=True, title='Динамика по годам',
        labels={'value': 'Сумма, $', 'year': 'Год', 'variable': 'Показатель'}
    )
    fig.update_layout(legend_title_text='', hovermode='x unified', height=500,
                      margin=dict(l=40, r=20, t=60, b=40))
    return fig

# ---------- Круговая диаграмма ----------
def build_pie_chart(year=None, region=None, category=None):
    filtered = filter_df(year, region, category)
    grouped = filtered.groupby('category').agg(total_sales=('sales', 'sum')).reset_index()
    fig = px.pie(grouped, values='total_sales', names='category',
                 title='Доля категорий в выручке', hole=0.4,
                 color='category', color_discrete_map=CATEGORY_COLORS)
    fig.update_layout(height=500, margin=dict(l=20, r=20, t=60, b=20))
    return fig

# ---------- Тепловая карта: регион × категория (на вкладке "Обзор") ----------
def build_heatmap(year=None, region=None, category=None):
    filtered = filter_df(year, region, category)

    grouped = filtered.groupby(['region', 'category']).agg(
        total_sales=('sales', 'sum'),
        total_profit=('profit', 'sum'),
    ).reset_index()

    grouped['margin_pct'] = (grouped['total_profit'] / grouped['total_sales'] * 100)

    pivot = grouped.pivot(index='region', columns='category', values='margin_pct')

    fig = px.imshow(
        pivot,
        text_auto='.2f',
        aspect='auto',
        color_continuous_scale='RdYlGn',
        zmin=-5, zmax=25,
        title='Маржа по региону и категории, %',
        labels={'color': 'Маржа, %'},
    )
    fig.update_layout(height=400, margin=dict(l=40, r=20, t=60, b=40))
    return fig

# ---------- Scatter: скидка vs маржа (только Central) ----------
def build_scatter_chart(year=None):
    central = df[df['region'] == 'Central']
    if year and year != 'all':
        central = central[central['year'] == int(year)]

    grouped = central.groupby(['sub_category', 'category']).agg(
        avg_discount=('discount', 'mean'),
        total_sales=('sales', 'sum'),
        total_profit=('profit', 'sum'),
    ).reset_index()

    grouped['avg_discount'] = grouped['avg_discount'] * 100
    grouped['margin_pct'] = (grouped['total_profit'] / grouped['total_sales'] * 100)

    fig = px.scatter(
        grouped, x='avg_discount', y='margin_pct',
        size='total_sales', color='category',
        color_discrete_map=CATEGORY_COLORS,
        hover_name='sub_category',
        title='Central: каждая точка — подкатегория',
        labels={'avg_discount': 'Средняя скидка, %',
                'margin_pct': 'Маржа, %',
                'category': 'Категория'},
    )
    fig.update_layout(height=500, margin=dict(l=40, r=20, t=60, b=40))
    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.6)
    return fig

# ---------- Таблица топ-убыточных подкатегорий (только Central) ----------
def build_loss_table(year=None):
    central = df[df['region'] == 'Central']
    if year and year != 'all':
        central = central[central['year'] == int(year)]

    grouped = central.groupby('sub_category').agg(
        avg_discount=('discount', 'mean'),
        total_sales=('sales', 'sum'),
        total_profit=('profit', 'sum'),
    ).reset_index()

    grouped['avg_discount'] = grouped['avg_discount'] * 100
    grouped['margin_pct'] = (grouped['total_profit'] / grouped['total_sales'] * 100)

    loss = grouped[grouped['total_profit'] < 0].sort_values('total_profit').head(7)

    rows = []
    for _, r in loss.iterrows():
        rows.append(html.Tr([
            html.Td(r['sub_category'], style={'padding': '8px', 'fontWeight': 'bold'}),
            html.Td(f"{r['avg_discount']:.1f}%", style={'padding': '8px', 'textAlign': 'right'}),
            html.Td(f"${r['total_sales']:,.0f}", style={'padding': '8px', 'textAlign': 'right'}),
            html.Td(f"${r['total_profit']:,.0f}", style={'padding': '8px', 'textAlign': 'right', 'color': '#c62828'}),
            html.Td(f"{r['margin_pct']:.1f}%", style={'padding': '8px', 'textAlign': 'right', 'color': '#c62828'}),
        ]))

    header = html.Tr([
        html.Th('Подкатегория', style={'padding': '10px', 'textAlign': 'left', 'backgroundColor': '#f0f2f5'}),
        html.Th('Ср. скидка', style={'padding': '10px', 'textAlign': 'right', 'backgroundColor': '#f0f2f5'}),
        html.Th('Выручка', style={'padding': '10px', 'textAlign': 'right', 'backgroundColor': '#f0f2f5'}),
        html.Th('Прибыль', style={'padding': '10px', 'textAlign': 'right', 'backgroundColor': '#f0f2f5'}),
        html.Th('Маржа', style={'padding': '10px', 'textAlign': 'right', 'backgroundColor': '#f0f2f5'}),
    ])

    table = html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': 14}
    )
    return table

# ---------- Карточка KPI ----------
def kpi_card(title, id_value):
    return html.Div([
        html.P(title, style={'fontSize': 14, 'color': '#666', 'marginBottom': 4}),
        html.H3('', id=id_value, style={'margin': 0, 'color': '#1a73e8'}),
    ], style={
        'flex': 1, 'padding': 20, 'backgroundColor': '#f5f7fb',
        'borderRadius': 10, 'textAlign': 'center',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
    })

# ---------- Приложение ----------
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1('Анализ продаж Superstore', style={'textAlign': 'center'}),

    dcc.Tabs([

        # ========== ВКЛАДКА 1: ОБЗОР ==========
        dcc.Tab(label='Обзор', children=[
            html.Div([

                html.H2('Общая картина'),

                # Фильтры
                html.Div([
                    dcc.Dropdown(id='filter-year',
                        options=[{'label': 'Все годы', 'value': 'all'}] +
                                [{'label': str(y), 'value': str(y)} for y in years],
                        value='all', clearable=False, style={'width': 200}),
                    dcc.Dropdown(id='filter-region',
                        options=[{'label': 'Все регионы', 'value': 'all'}] +
                                [{'label': r, 'value': r} for r in regions],
                        value='all', clearable=False, style={'width': 200}),
                    dcc.Dropdown(id='filter-category',
                        options=[{'label': 'Все категории', 'value': 'all'}] +
                                [{'label': c, 'value': c} for c in categories],
                        value='all', clearable=False, style={'width': 200}),
                ], style={'display': 'flex', 'gap': 16, 'marginBottom': 40}),

                # KPI-карточки
                html.Div([
                    kpi_card('Выручка', 'kpi-sales'),
                    kpi_card('Прибыль', 'kpi-profit'),
                    kpi_card('Маржа', 'kpi-margin'),
                    kpi_card('Заказы', 'kpi-orders'),
                ], style={'display': 'flex', 'gap': 16, 'marginBottom': 40}),

                # Графики динамики и pie
                html.Div([
                    html.Div([dcc.Graph(id='dynamics-chart', style={'height': '500px'})], style={'flex': 2}),
                    html.Div([dcc.Graph(id='pie-chart', style={'height': '500px'})], style={'flex': 1}),
                ], style={'display': 'flex', 'gap': 16, 'marginBottom': 40}),

                # Тепловая карта
                html.H3('Тепловая карта: маржа по региону и категории'),
                html.Div([
                    dcc.Graph(id='heatmap-chart', style={'height': '400px'}),
                ]),

            ])
        ]),

        # ========== ВКЛАДКА 2: ПРОБЛЕМЫ CENTRAL ==========
        dcc.Tab(label='Проблемы Central', children=[
            html.Div([
                html.H2('Где мы теряем деньги'),

                # Свой фильтр года
                html.Div([
                    html.Label('Год:', style={'marginRight': 10, 'fontWeight': 'bold'}),
                    dcc.Dropdown(id='central-year-filter',
                        options=[{'label': 'Все годы', 'value': 'all'}] +
                                [{'label': str(y), 'value': str(y)} for y in years],
                        value='all', clearable=False, style={'width': 200}),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': 20}),

                html.P(
                    'Центральный регион: каждая точка — подкатегория. '
                    'По оси X — средняя скидка, по оси Y — маржа. '
                    'Точки ниже пунктирной линии — убыточные. '
                    'Размер точки — выручка подкатегории.',
                    style={'color': '#555', 'marginBottom': 20}
                ),

                # Scatter
                html.Div([
                    dcc.Graph(id='scatter-chart', style={'height': '500px'}),
                ], style={'marginBottom': 40}),

                # Таблица
                html.H3('Топ-7 убыточных подкатегорий в Central'),
                html.Div(id='loss-table'),

            ])
        ]),

    ])
])

# ---------- Callbacks: вкладка ОБЗОР ----------
@app.callback(
    Output('kpi-sales', 'children'),
    Output('kpi-profit', 'children'),
    Output('kpi-margin', 'children'),
    Output('kpi-orders', 'children'),
    Input('filter-year', 'value'),
    Input('filter-region', 'value'),
    Input('filter-category', 'value'),
)
def update_kpi(year, region, category):
    sales, profit, margin, orders = calculate_kpi(year, region, category)
    return (f'${sales:,.0f}', f'${profit:,.0f}', f'{margin:.2f}%', f'{orders:,}')

@app.callback(
    Output('dynamics-chart', 'figure'),
    Input('filter-year', 'value'),
    Input('filter-region', 'value'),
    Input('filter-category', 'value'),
)
def update_dynamics(year, region, category):
    return build_dynamics_chart(year, region, category)

@app.callback(
    Output('pie-chart', 'figure'),
    Input('filter-year', 'value'),
    Input('filter-region', 'value'),
    Input('filter-category', 'value'),
)
def update_pie(year, region, category):
    return build_pie_chart(year, region, category)

@app.callback(
    Output('heatmap-chart', 'figure'),
    Input('filter-year', 'value'),
    Input('filter-region', 'value'),
    Input('filter-category', 'value'),
)
def update_heatmap(year, region, category):
    return build_heatmap(year, region, category)

# ---------- Callbacks: вкладка ПРОБЛЕМЫ CENTRAL ----------
@app.callback(
    Output('scatter-chart', 'figure'),
    Input('central-year-filter', 'value'),
)
def update_scatter(year):
    return build_scatter_chart(year)

@app.callback(
    Output('loss-table', 'children'),
    Input('central-year-filter', 'value'),
)
def update_loss_table(year):
    return build_loss_table(year)

if __name__ == '__main__':
    app.run(debug=True)