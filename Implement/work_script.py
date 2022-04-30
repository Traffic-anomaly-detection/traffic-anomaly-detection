import datetime
import pytz
import requests
import pandas as pd
import joblib
import json
import schedule
import time

interval = 10

header_list = ['datetime', 'road_number', 'km', 'direction', 'all_units', 'inflow_units',
               'outflow_unit', 'samecell_units', 'avg_speed', 'max_speed', 'avg_traveltime', 'max_traveltime']

num_cols = ['all_units', 'inflow_units',
            'portion_speed', 'max_speed',
            'avg_traveltime', 'max_traveltime']

list_road = [1,2,7]
list_direction = ["in","out"]

df_km127 = pd.read_csv("../dataset/latlon_km127.csv")

pd.options.mode.chained_assignment = None  # default='warn'

def map_traffic_with_latlon(df):
    df['lat'] = df.apply(lambda row: df_km127[(df_km127['rd'] == row['road_number']) & (df_km127['km'] == row['km'])]['lat'].values[0]
                         if len(df_km127[(df_km127['rd'] == row['road_number']) & (df_km127['km'] == row['km'])]['lat'].values) > 0 else 0, axis=1)
    df['lon'] = df.apply(lambda row: df_km127[(df_km127['rd'] == row['road_number']) & (df_km127['km'] == row['km'])]['lon'].values[0]
                         if len(df_km127[(df_km127['rd'] == row['road_number']) & (df_km127['km'] == row['km'])]['lon'].values) > 0 else 0, axis=1)
    return df

def lineNotify(post_data):
    headers = {
        'content-type':
        'application/x-www-form-urlencoded',
        'Authorization': 'Bearer ' + 'Rr0wbQYQhq07gzE0knhSSbFNFAS8UtCfoFNX5H5uBSm'
    }
    msg = f'{post_data[10]} Anomaly at \nRoad number : {post_data[0]} \nKm : {post_data[1]} \nDirection : {post_data[2]}\nLatitude : {post_data[8]} \nLongitude : {post_data[9]} \n'
    glink = f'https://www.google.com/maps/dir//{post_data[8]}+,+{post_data[9]}'
    send_msg = f'{msg}{glink}'
    r = requests.post('https://notify-api.line.me/api/notify',
                      headers=headers, data={'message': send_msg})

def job():
    now = datetime.datetime.now()
    print('***REQUESTING NEW DATA********************************')
    print('REQUESTING AT : ' + str(now))
    print('Begin predicting ....')
    for road in list_road :
        for direction in list_direction :
            
            sus_cluster = None
            if road == 1 : 
                sus_cluster = 1 if direction == 'in' else 0
            elif road == 2 : 
                sus_cluster = 1 if direction == 'in' else 0
            elif road == 7 : 
                sus_cluster = 0 if direction == 'in' else 2

            
            print(f'Predicting road {road} : {direction} ....')
            gnb_model = joblib.load(f'../Models/GaussianNBModelRoad{road}{direction}.joblib')
            road_data = pd.read_csv("http://analytics2.dlt.transcodeglobal.com/cell_data/current_celldata.csv",names=header_list)
            dfm = pd.read_csv(f'../dataset/road{road}-{direction}-mffs.csv')
            road_data = road_data[(road_data['road_number'] == road)]
            road_data['mffs'] = road_data['km'].map(dfm.set_index('km')['mffs'])
            road_data = map_traffic_with_latlon(road_data)
            current_data = road_data[(road_data['road_number']==road) & (road_data['direction']==direction)]
            current_data['portion_speed'] = current_data['avg_speed']/current_data['mffs']

            x_predict = current_data[num_cols]
            y_predict = gnb_model.predict(x_predict)
            current_data['cluster'] = y_predict
            y_predict_proba = gnb_model.predict_proba(x_predict)

            problist = []
            for i in y_predict_proba :
                problist.append(round(i[sus_cluster],3))
            current_data['prob'] = problist
            current_data = current_data[(current_data['cluster']==sus_cluster) & (current_data['prob']>=0.8) & (current_data['all_units']>=1) & (current_data['avg_speed']>0)]
            if current_data.empty :
                post_data = []
            else :              
                post_data = current_data[['road_number','km','direction','inflow_units','outflow_unit','samecell_units','all_units','avg_speed','lat','lon','datetime']]
                # post_data['datetime'] = post_data['datetime'].dt.tz_localize('Etc/GMT+7').dt.tz_convert('America/New_York')
                # print(post_data.dtypes)
                post_data = post_data.values.tolist()

            

            

            

            url = 'https://tad-api-v1.herokuapp.com/api/accident/bulk'

            print(f'Prediction of road {road} : {direction} : DONE ...')
            if len(post_data) != 0 :
                print(post_data[0][-1])

                result = requests.post(url, json=post_data)
                
                print(f'Posting to Backend {len(post_data)} items')
                print(f'Status code : {result.status_code} , reason : {result.reason}')
            else :
                print(f'Not Detect anomaly, skipping ....')

            # if(post_data) :
            #     for i in post_data :
            #         lineNotify(i)

            print('------------------------------------')

            
    print('PROCESS SUCCESS....')
    print('NEXT REQUEST AT : ' + str(now + datetime.timedelta(minutes=interval)))
    print('******************************************************\n\n\n')
    return

job()

schedule.every(interval).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(0) 

              






