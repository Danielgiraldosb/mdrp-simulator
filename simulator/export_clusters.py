import pandas as pd
import json

df = pd.read_csv('instance_clusters.csv')

labels = {
    0: 'Dispersas, con holgura',
    1: 'Pequeñas y compactas',
    2: 'Medianas y cargadas',
    3: 'Grandes y saturadas',
}
df['cluster_label'] = df['cluster'].map(labels)

cols = ['instance', 'cluster', 'cluster_label', 'size', 'speed', 'schedule', 'prep', 'seed',
       'n_orders', 'n_couriers', 'n_restaurants', 'orders_per_courier_hour',
       'degree_of_dynamism', 'delivery_dist_m_mean', 'restaurant_spacing_m_mean',
       'preparation_mean', 'meters_per_minute']
out = df[cols].round(4).to_dict(orient='records')

scratch = r'C:\Users\danie\AppData\Local\Temp\claude\C--Users-danie\a0473f97-8406-49ea-a4ff-152c2032a54c\scratchpad'
with open(scratch + r'\instance_clusters_data.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print('wrote', len(out), 'rows')
