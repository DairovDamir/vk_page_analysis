import pandas as pd
import vk_api
from config_file import vk_token
import psycopg2
from psycopg2.extras import execute_values
import clickhouse_connect

try:
    vk_session = vk_api.VkApi(token=vk_token)
    vk = vk_session.get_api()
except Exception as e:
    print('Ошибка подключения:', e)

try:
    data = vk.wall.get(domain = 'dm', count = 100)
    posts = data['items']
except Exception as e:
    print('Ошибка при чтении со страницы:', e)

df = pd.DataFrame([{
    'date': pd.to_datetime(post.get('date'), unit='s'),
    'text': post.get('text', ''),
    'likes': post.get('likes', {}).get('count', 0),
} for post in posts])

try:
    with psycopg2.connect(
            dbname="vk_analysis_db",
            user="postgres",
            password="postgres",
            host="localhost",
            port="5432"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                TRUNCATE TABLE table1;
            ''')
            cur.execute('''
            	CREATE TABLE IF NOT EXISTS table1 (
                	id SERIAL PRIMARY KEY,
                	date TIMESTAMP,
                	text VARCHAR(50),
                	likes INTEGER
            	);
        	''')
            data_tuples = []
            for index, row in df.iterrows():
                text_trimmed = row['text'][:50]
                data_tuples.append((row['date'], text_trimmed, row['likes']))

            execute_values(
                cur,
                "INSERT INTO table1 (date, text, likes) VALUES %s",
                data_tuples
            )

            conn.commit()
except Exception as e:
    print('Ошибка при подключении к PostgreSQL:', e)

try:
    client = clickhouse_connect.get_client(
        host='localhost',
        port=8123,
        username='admin',
        password='password',
        database='vk_analysis_db'
    )

    client.command('''CREATE TABLE IF NOT EXISTS vk_analysis_db.table1 (
                    id Int32,
                    date DateTime,
                    text String,
                    likes Int32
                ) ENGINE = MergeTree()
                    ORDER BY (id);''')

    client.insert_df(df=df, table='table1', database='vk_analysis_db')
except Exception as e:
    print('Ошибка при подключении к Clickhouse:', e)

df.to_csv('vk_posts_new_table.csv')