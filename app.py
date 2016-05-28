#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, jsonify
from flask.ext.wtf import Form
from flask_wtf.csrf import CsrfProtect
from wtforms import StringField, DateTimeField, IntegerField
from wtforms.validators import DataRequired
import numpy as np
import pandas as pd
from bokeh.plotting import figure
from bokeh.charts import Line
from bokeh.embed import components
import requests
import dill
import ujson
from time import strftime
import datetime
import sys
import logging

app = Flask(__name__)
# app.config.from_object('config')
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)
app.vars = {'interval': 15}
app.secret_key = 'Zsdfj389'
CsrfProtect(app)


# Some helper functions

# Definition of the web form here.


class UserInput(Form):
    interval = IntegerField('Interval (min): ', validators=[DataRequired()],
                            default=15)
    start = DateTimeField('Start date/time is: ', validators=[DataRequired()],
                          format='%Y-%m-%dT%H:%M:%S',
                          default=datetime.datetime(2015, 9, 11, 00, 00, 00))
    end = DateTimeField('End date/time is: ', validators=[DataRequired()],
                        format='%Y-%m-%dT%H:%M:%S',
                        default=datetime.datetime(2015, 9, 13, 00, 00, 00))


def _flatten_dict(root_key, nested_dict, flattened_dict):
    for key, value in nested_dict.items():
        next_key = root_key + "_" + key if root_key != "" else key
        if isinstance(value, dict):
            _flatten_dict(next_key, value, flattened_dict)
        else:
            flattened_dict[next_key] = value
    return flattened_dict


def nyc_current():
    response = requests.get('http://api.prod.obanyc.com/api/siri/vehicle-monitoring.json',
                            params=dict(
                                key='0a01eb19-991f-4e02-b093-2999ce81fcb2')
                            ).json()
    info = response['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'][0]['VehicleActivity']
    return pd.DataFrame([_flatten_dict('', i, {}) for i in info])


def dataframe_to_geojson(dataframe):
    '''
    Turn pandas dataframe into GeoJSON object
    '''
    result = {}
    result["type"] = 'FeatureCollection'
    features = []
    for num, row in dataframe.iterrows():
        feature = {}
        feature['type'] = 'Feature'
        feature['properties'] = dict({'popupContent': row['name']})
        feature['geometry'] = dict({'type': 'Point', 'coordinates': [row['longitude'],
                                                                     row['latitude']]})
        features.append(feature)
    result['features'] = features
    return result


@app.route('/')
def main():
    return render_template('index.html')


@app.route('/static', methods=['GET', 'POST'])
def static_render():
    form = UserInput()
    date_format_str = "%Y-%m-%dT%H:%M:%S"
    with open('vehicle_time.pk', 'rb') as f:
        database = dill.load(f)
    if request.method == 'GET':
        startime = pd.datetime.strptime('2015-09-11T00:00:00', date_format_str)
        endtime = pd.datetime.strptime('2015-09-13T00:00:00', date_format_str)
        subset = database[(startime < database.index) & (database.index < endtime)]
        result = subset.resample(str(app.vars['interval']) + 'min').nunique()
        p1 = figure(x_axis_type='datetime')
        p1.quad(top=result.values, bottom=0,
                left=result.index - np.timedelta64(int(app.vars['interval'] / 2), 'm'),
                right=result.index + np.timedelta64(int(app.vars['interval'] / 2), 'm'))
        p1.xaxis.axis_label = 'Time'
        p1.yaxis.axis_label = 'Number'
        scripts, divs = components(p1)
        return render_template('static.html', script=scripts, div=divs,
                               interval=str(app.vars['interval']),
                               startime_str='2015-09-11T00:00:00',
                               endtime_str='2015-09-13T00:00:00',
                               form=form)
    else:
        if form.validate_on_submit():
            app.vars['interval'] = int(form.interval.data)
            startime = form.start.data
            endtime = form.end.data
            subset = database[(startime < database.index) & (database.index < endtime)]
            result = subset.resample(str(app.vars['interval']) + 'min').nunique()
            p1 = figure(x_axis_type='datetime')
            p1.quad(top=result.values, bottom=0, left=result.index -
                    np.timedelta64(int(0.75 * app.vars['interval'] / 2), 'm'),
                    right=result.index + np.timedelta64(int(0.75 *
                                                            app.vars['interval'] / 2),
                                                        'm'))
            p1.xaxis.axis_label = 'Time'
            p1.yaxis.axis_label = 'Number'
            scripts, divs = components(p1)
            return render_template('static.html', script=scripts, div=divs,
                                   interval=str(app.vars['interval']),
                                   startime_str=request.form['start'],
                                   endtime_str=request.form['end'],
                                   form=form)
        else:
            return redirect('/static')


@app.route('/live')
def live():
    bus_info = nyc_current().ix[:,
                                ('MonitoredVehicleJourney_PublishedLineName',
                                 'MonitoredVehicleJourney_VehicleLocation_Latitude',
                                 'MonitoredVehicleJourney_VehicleLocation_Longitude')]
    bus_info.columns = ['name', 'latitude', 'longitude']
    lat_mean = bus_info['latitude'].mean()
    log_mean = bus_info['longitude'].mean()
    bus_info_json = dataframe_to_geojson(bus_info)
    bus_number = len(bus_info)
    time_string = strftime("%Y-%m-%d %H:%M:%S")
    return render_template('live.html', number=bus_number, time=time_string,
                           points=bus_info_json, x_mean=lat_mean, y_mean=log_mean)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=33507)
