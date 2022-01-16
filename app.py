from flask import Flask, render_template, url_for, request, Response
import pandas as pd
from datetime import timezone, datetime, timedelta
import json
import plotly
import numpy as np
import plotly.express as px
import os

app = Flask(__name__)
dir_path = os.path.dirname(__file__)

# datetime setting
local_tz = timezone(timedelta(hours=+8))


def get_data():
    target = ['石門水庫', '新山水庫', '翡翠水庫', '寶山第二水庫', '永和山水庫', '明德水庫',
              '鯉魚潭水庫', '湖山水庫', '仁義潭水庫', '白河水庫', '烏山頭水庫', '曾文水庫',
              '南化水庫', '阿公店水庫', '牡丹水庫', '德基水庫', '霧社水庫', '日月潭水庫',
              '石岡壩', '高屏溪攔河堰']  # 排除集集攔河堰（資料較不穩定）
    data = []

    for y in range(2019, 2022):
        year_data = pd.read_csv(dir_path + '/data/reservoir_{}.csv'.format(y))
        year_data = year_data[year_data['ReservoirName'].isin(target)]
        data.append(year_data)

    df = pd.concat(data)
    df = df[~df['EffectiveWaterStorageCapacity'].isnull()]
    df = df.reset_index().drop('index', axis=1)
    df = df.sort_values('RecordTime')
    df['RecordTime'] = pd.to_datetime(df['RecordTime'], format='%Y-%m-%d')
    df['Year'] = df['RecordTime'].apply(lambda x: str(x.date().strftime('%Y')))
    return df


def data_cleaning(dataframe):
    df_clean = dataframe
    df_clean.loc[(~np.isfinite(df_clean['WaterStorageRate']))] = np.nan
    df_clean.loc[df_clean['WaterStorageRate'] > 1, 'WaterStorageRate'] = 1
    df_clean.loc[df_clean['WaterStorageRate'] > 1.5, 'WaterStorageRate'] = np.nan
    df_clean = df_clean[~df_clean['WaterStorageRate'].isnull()]
    df_clean['date'] = df_clean['RecordTime'].apply(lambda x: x.date().strftime('%m-%d'))
    df_clean['date'] = pd.to_datetime(df_clean['date'], format='%m-%d', errors='coerce')

    return df_clean


def reservoir_sum_by_year(raw_data):
    df_year = raw_data.groupby(['RecordTime', 'Year'])[
        ['EffectiveCapacity', 'EffectiveWaterStorageCapacity']].sum().reset_index()
    df_year['WaterStorageRate'] = df_year['EffectiveWaterStorageCapacity'] / df_year['EffectiveCapacity']
    df_year = data_cleaning(df_year)

    return df_year


def reservoir_by_name(raw_data, reservoir_name):
    df_name = raw_data[raw_data['ReservoirName'] == reservoir_name]
    df_name['WaterStorageRate'] = df_name['WaterStorageRate'] / 100
    df_name['WaterStorageRate'] = df_name['WaterStorageRate'].where(df_name['WaterStorageRate'].isnull(),
                                                                    df_name['EffectiveWaterStorageCapacity'] /
                                                                    df_name['EffectiveCapacity'])
    df_name = data_cleaning(df_name)

    return df_name


def get_plotly_json(graph_data, x_axis='date', y_axis='WaterStorageRate'):
    # last date
    last_date = graph_data['RecordTime'].to_list()[-1].date().strftime('%Y')

    fig = px.line(graph_data, x=x_axis, y=y_axis,
                  color='Year', template='simple_white')
    fig.update_traces({'line': {'color': 'lightgrey'}})
    fig.update_traces(hovertemplate='日期: %{x|%m-%d}<br>蓄水率: %{y}', )
    fig.update_traces(patch={'line': {'color': 'rgb(250, 149, 137)', 'width': 3}},
                      selector={'legendgroup': '2021'},
                      secondary_y=False)

    # add label on latest value
    fig.add_scatter(x=[fig.data[-1].x[-1]], y=[fig.data[-1].y[-1]],
                    mode='markers + text',
                    marker={'color': 'rgb(250, 149, 137)', 'size': 2},
                    showlegend=False,
                    text=last_date,
                    textposition='top center',
                    hovertemplate='',
                    hoverinfo='skip',)

    fig.update_layout(
        title='',
        plot_bgcolor='rgb(250, 250, 250)',
        paper_bgcolor='rgb(250, 250, 250)',
        yaxis_tickformat='%',
        yaxis_range=[0, 1.02],
        xaxis_tickformat='%m',
        yaxis_title='蓄水率',
        xaxis_title='月份',
        showlegend=False,
        margin=dict(t=10, l=10, b=10, r=10),
        legend=dict(
            orientation='h',
            y=1.1,
        )
    )

    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graph_json


@app.route('/', methods=['GET'])
def plot_plotly():
    reservoir_data = get_data()
    graph_json = []

    # first figure
    reservoir_yearly = reservoir_sum_by_year(reservoir_data)
    graph_json_main = get_plotly_json(reservoir_yearly)

    # second figure
    meta = []
    for i, t in enumerate(reservoir_data['ReservoirName'].unique()):
        reservoir_each = reservoir_by_name(reservoir_data, t)
        latest_value = reservoir_each.iloc[-1:, :]

        if not reservoir_each.empty and latest_value['WaterStorageRate'].item() < .5:
            meta_info = (t, '{:.2f}'.format(latest_value['WaterStorageRate'].item()*100), latest_value['RecordTime'].item().date().strftime('%Y-%m-%d'), 'graph-{}'.format(i))
            graph_json_each = get_plotly_json(reservoir_each)
            graph_json.append(graph_json_each)
            meta.append(meta_info)

    reservoir_low_water_level = '、'.join([i[0] for i in meta])

    return render_template('index.html',
                           meta_title='DSSI DEMO',
                           page_route='',
                           graph_json_main=graph_json_main,
                           graph_json_each=graph_json,
                           meta=meta,
                           reservoir_low_water_level=reservoir_low_water_level)


@app.route('/all_plot', methods=['GET'])
def plot_plotly_all():
    reservoir_data = get_data()
    graph_json_all = []
    meta_all = []

    for i, t in enumerate(reservoir_data['ReservoirName'].unique()):
        reservoir_each = reservoir_by_name(reservoir_data, t)
        latest_value = reservoir_each.iloc[-1:, :]

        if not reservoir_each.empty:
            meta_info = (t,
                         '{:.2f}'.format(latest_value['WaterStorageRate'].item()*100),
                         latest_value['RecordTime'].item().date().strftime('%Y-%m-%d'),
                         'graph-{}'.format(i))
            graph_json_each = get_plotly_json(reservoir_each)
            graph_json_all.append(graph_json_each)
            meta_all.append(meta_info)

    return render_template('all_reservoir.html',
                           meta_title='DSSI Demo',
                           page_route='all_plot',
                           graph_json_all=graph_json_all,
                           meta_all=meta_all)


@app.route('/data', methods=['GET'])
def raw_data():
    # some query parameters
    reservoir_name = request.args.get('name', None)
    limit = request.args.get('limit', 100)

    # data for response
    all_resv = get_data()
    if reservoir_name:
        all_resv = all_resv[all_resv['ReservoirName'] == reservoir_name]

    if not limit == 'none':
        all_resv = all_resv.iloc[-limit:, :]

    response_data = all_resv.to_json(orient='records')
    response = Response(response_data, mimetype='application/json')

    return response


if __name__ == '__main__':
    app.run()

