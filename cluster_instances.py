"""
Data-driven clustering of the 240 mdrplib instances by their ACTUAL measured
characteristics (from each instance's own instance_characteristics.txt),
not just the nominal factorial-design labels (size/speed/schedule/prep) --
those labels turn out to be a poor proxy for real difficulty, since the
leading seed digit alone swings order volume by >10x within the same
nominal "size" category (e.g. '0o100...' has 505 orders, '7o100...' has
3,213) and degree of dynamism from 0.30 to 0.6+.

Produces:
  - instance_clusters.csv: one row per instance with its raw/derived
    features and assigned cluster id.
  - cluster_profiles.json: per-cluster centroid characteristics in
    ORIGINAL units (not standardized), for human-readable labeling.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from run import DEFAULT_INSTANCES_DIR as INSTANCES_DIR
NAME_RE = re.compile(r'^(\d+)(o100|o50|r50)(t100|t75)(s1|s2)(p100|p125)$')


def parse_characteristics(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        text = f.read()
    out = {}
    for key, pattern in [
        ('n_orders', r'number of orders:\s*(\d+)'),
        ('n_restaurants', r'number of restaurants:\s*(\d+)'),
        ('n_couriers', r'number of couriers:\s*(\d+)'),
        ('total_courier_hours', r'total courier hours:\s*([\d.]+)'),
        ('operating_period_min', r'operating period \(minutes\):\s*([\d.]+)'),
        ('degree_of_dynamism', r'degree of dynamism:\s*([\d.]+)'),
    ]:
        m = re.search(pattern, text)
        out[key] = float(m.group(1)) if m else None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'meters from restaurant to delivery location' in line:
            cols = re.split(r'\s{2,}', line.strip())
            mean_line = lines[i + 1]
            vals = [float(v) for v in re.findall(r'[-+]?\d*\.?\d+', mean_line)]
            for c, v in zip(cols, vals):
                if 'meters' in c:
                    out['delivery_dist_m_mean'] = v
                elif 'minutes' in c:
                    out['delivery_time_min_mean'] = v
        elif 'meters between restaurants' in line:
            cols = re.split(r'\s{2,}', line.strip())
            mean_line = lines[i + 1]
            vals = [float(v) for v in re.findall(r'[-+]?\d*\.?\d+', mean_line)]
            for c, v in zip(cols, vals):
                if 'meters' in c:
                    out['restaurant_spacing_m_mean'] = v
        elif line.strip().startswith('preparation') and 'soft_response_time' in line:
            cols = re.split(r'\s{2,}', line.strip())
            mean_line = lines[i + 1]
            vals = [float(v) for v in re.findall(r'[-+]?\d*\.?\d+', mean_line)]
            for c, v in zip(cols, vals):
                out[f'{c}_mean'] = v
        i += 1
    return out


def parse_parameters(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    header = lines[0].split('\t')
    values = lines[1].split('\t')
    d = dict(zip(header, values))
    return {'meters_per_minute': float(d['meters_per_minute'])}


if __name__ == '__main__':
    rows = []
    for name in sorted(os.listdir(INSTANCES_DIR)):
        m = NAME_RE.match(name)
        if not m:
            continue
        seed, size, speed, schedule, prep = m.groups()
        inst_dir = os.path.join(INSTANCES_DIR, name)
        feats = parse_characteristics(os.path.join(inst_dir, 'instance_characteristics.txt'))
        feats.update(parse_parameters(os.path.join(inst_dir, 'instance_parameters.txt')))
        feats['instance'] = name
        feats['seed'] = int(seed)
        feats['size'] = size
        feats['speed'] = speed
        feats['schedule'] = schedule
        feats['prep'] = prep
        rows.append(feats)

    df = pd.DataFrame(rows)
    print(f"Parsed {len(df)} instances. Columns: {list(df.columns)}")

    df['orders_per_courier_hour'] = df['n_orders'] / df['total_courier_hours']
    df['orders_per_restaurant'] = df['n_orders'] / df['n_restaurants']
    df['couriers_per_restaurant'] = df['n_couriers'] / df['n_restaurants']

    feature_cols = [
        'n_orders', 'n_couriers', 'n_restaurants',
        'orders_per_courier_hour', 'degree_of_dynamism',
        'delivery_dist_m_mean', 'restaurant_spacing_m_mean',
        'preparation_mean', 'meters_per_minute',
    ]
    print("\nFeature summary:")
    print(df[feature_cols].describe().T[['mean', 'std', 'min', 'max']])

    X = df[feature_cols].values
    Xs = StandardScaler().fit_transform(X)

    print("\nSilhouette scores by k:")
    best_k, best_score = None, -1
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
        score = silhouette_score(Xs, km.labels_)
        print(f"  k={k}: silhouette={score:.4f}")
        if score > best_score:
            best_k, best_score = k, score

    print(f"\nChosen k={best_k} (best silhouette={best_score:.4f})")
    km = KMeans(n_clusters=best_k, n_init=10, random_state=42).fit(Xs)
    df['cluster'] = km.labels_

    # Order clusters by a difficulty proxy (orders_per_courier_hour) so
    # cluster ids read low-to-high "load", not an arbitrary KMeans order.
    relabel = {old_cluster: new_id for new_id, old_cluster in
              enumerate(df.groupby('cluster')['orders_per_courier_hour'].mean().sort_values().index)}
    df['cluster'] = df['cluster'].map(relabel)

    print("\nCluster sizes:")
    print(df['cluster'].value_counts().sort_index())

    print("\nCluster profiles (mean of each feature):")
    profile = df.groupby('cluster')[feature_cols].mean()
    print(profile)

    print("\nCluster composition vs nominal size label:")
    print(pd.crosstab(df['cluster'], df['size']))
    print("\nCluster composition vs seed:")
    print(pd.crosstab(df['cluster'], df['seed']))

    df.to_csv('instance_clusters.csv', index=False)

    profiles_out = {}
    for c in sorted(df['cluster'].unique()):
        sub = df[df['cluster'] == c]
        profiles_out[int(c)] = {
            'n_instances': int(len(sub)),
            **{col: round(float(sub[col].mean()), 3) for col in feature_cols},
            'size_breakdown': sub['size'].value_counts().to_dict(),
            'seed_breakdown': sorted(sub['seed'].unique().tolist()),
        }
    with open('cluster_profiles.json', 'w', encoding='utf-8') as f:
        json.dump(profiles_out, f, indent=2, ensure_ascii=False)

    print(f"\nWrote instance_clusters.csv ({len(df)} rows) and cluster_profiles.json")
