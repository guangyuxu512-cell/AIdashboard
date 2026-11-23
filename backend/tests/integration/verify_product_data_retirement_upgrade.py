"""Exercise 0059 only against a deliberately empty disposable Feature DB."""
from pathlib import Path
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from psycopg import connect
from psycopg.types.json import Json, Jsonb
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings

url = make_url(str(get_settings().database_url))
if url.database != 'control_center_feat_retire_product_data_upgrade':
    raise RuntimeError('This check requires its dedicated disposable Feature database')
dsn = url.set(drivername='postgresql').render_as_string(hide_password=False)
with connect(dsn, connect_timeout=5) as connection:
    assert connection.execute('SELECT current_database()').fetchone()[0] == url.database
    assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0] == 0

config = Config(str(BACKEND / 'alembic.ini'))
config.set_main_option('script_location', str(BACKEND / 'migrations'))
command.upgrade(config, '20261121_0058')
ids = {name: str(uuid4()) for name in ('team', 'user', 'device', 'shop', 'product',
                                         'batch', 'series', 'generation', 'schedule', 'token')}
with connect(dsn, connect_timeout=5) as connection:
    connection.execute('INSERT INTO teams(team_id,name) VALUES (%s,%s)', (ids['team'], 'fixture'))
    connection.execute('INSERT INTO users(user_id,display_name) VALUES (%s,%s)', (ids['user'], 'fixture'))
    connection.execute('INSERT INTO devices(device_id,team_id,display_name) VALUES (%s,%s,%s)',
                       (ids['device'], ids['team'], 'fixture'))
    connection.execute('INSERT INTO historical_shop_identities(shop_id,display_name,platform) VALUES (%s,%s,%s)',
                       (ids['shop'], 'fixture', 'douyin'))
    connection.execute('INSERT INTO shop_product_data_products(shop_product_id,shop_id,platform,platform_product_id) '
                       'VALUES (%s,%s,%s,%s)', (ids['product'], ids['shop'], 'douyin', '123'))
    connection.execute('INSERT INTO shop_product_data_collection_batches '
        '(collection_batch_id,requested_by_user_id,submission_key,period,sale_type,content_type) '
        'VALUES (%s,%s,%s,%s,%s,%s)', (ids['batch'], ids['user'], str(uuid4()), '1d', '1', '1'))
    connection.execute('INSERT INTO shop_product_data_series '
        '(series_id,shop_id,rolling_series_hash,period,sale_type,content_type,request_contract,metric_contract) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
        (ids['series'], ids['shop'], 'a' * 64, '1d', '1', '1', 'fixture', 'fixture'))
    scope = {'shop_id': ids['shop'], 'period': '1d', 'start_date': '2026-01-01', 'end_date': '2026-01-01',
             'timezone': 'Asia/Shanghai', 'platform': 'douyin', 'sale_type': '1', 'content_type': '1',
             'request_contract': 'fixture', 'metric_contract': 'fixture'}
    connection.execute("""INSERT INTO shop_product_data_generations
        (generation_id,collection_batch_id,batch_position,series_id,shop_id,sequence,
         requested_by_user_id,submission_key,period,date_type,start_date,end_date,source_scope_hash,
         request_scope,status,stage,attempt_count,lease_id,lease_until,last_heartbeat_at,started_at)
        VALUES (%s,%s,0,%s,%s,1,%s,%s,'1d','20','2026-01-01','2026-01-01',%s,%s,
                'running','execution',1,%s,now()+interval '5 minutes',now(),now())""",
        (ids['generation'], ids['batch'], ids['series'], ids['shop'], ids['user'], str(uuid4()),
         'b' * 64, Jsonb(scope), str(uuid4())))
    connection.execute("""INSERT INTO schedules(schedule_id,team_id,created_by_user_id,name,enabled,
        target_device_id,skill_id,execution_display_name,schedule_type,local_time,timezone,task_input_json)
        VALUES (%s,%s,%s,%s,true,%s,'system.echo',%s,'daily','09:00','Asia/Shanghai',%s)""",
        (ids['schedule'], ids['team'], ids['user'], 'fixture', ids['device'], 'fixture', Jsonb({})))
    connection.execute('INSERT INTO api_tokens(token_id,owner_user_id,name,token_hash,permissions) '
        'VALUES (%s,%s,%s,%s,%s)', (ids['token'], ids['user'], 'fixture', '0' * 64,
        Json(['GET /api/v1/product-data', 'GET /api/v1/product-data/collection-shops', 'GET /api/v1/devices'])))

try:
    command.upgrade(config, 'head')
    raise AssertionError('active collection must block retirement')
except RuntimeError as error:
    assert 'active lease' in str(error)
with connect(dsn, connect_timeout=5) as connection:
    assert connection.execute('SELECT count(*) FROM shop_product_data_products').fetchone()[0] == 1
    assert connection.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '20261121_0058'
    connection.execute("UPDATE shop_product_data_generations SET status='failed', lease_id=NULL, lease_until=NULL, "
                       "finished_at=now(), failure_code='FIXTURE' WHERE generation_id=%s", (ids['generation'],))

command.upgrade(config, 'head')
with connect(dsn, connect_timeout=5) as connection:
    assert connection.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '20261124_0059'
    assert connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' "
                              "AND tablename LIKE 'shop_product_data_%'").fetchone()[0] == 0
    for table, column, key in (('historical_shop_identities', 'shop_id', 'shop'),
                                ('devices', 'device_id', 'device'), ('schedules', 'schedule_id', 'schedule')):
        assert connection.execute(f'SELECT count(*) FROM {table} WHERE {column}=%s', (ids[key],)).fetchone()[0] == 1
    assert connection.execute('SELECT permissions FROM api_tokens WHERE token_id=%s',
                              (ids['token'],)).fetchone()[0] == ['GET /api/v1/devices']
print('Product-data retirement guarded active work and preserved unrelated records')
