"""Daily real-data snapshot generator. No synthetic financial data."""
import json, os, time, datetime as dt, pathlib, urllib.parse, urllib.request, math
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'snapshot.json'
BASE='https://api.finmindtrade.com/api/v4/data'
TOKEN=os.getenv('FINMIND_TOKEN','').strip()
UA='TaiwanStockResearchPersonal/2.0'

def fetch(dataset, stock, start):
    params={'dataset':dataset,'data_id':stock,'start_date':start}
    if TOKEN:params['token']=TOKEN
    req=urllib.request.Request(BASE+'?'+urllib.parse.urlencode(params),headers={'User-Agent':UA,'Accept':'application/json'})
    last=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=35) as r: raw=json.load(r)
            if raw.get('status')!=200:raise RuntimeError(f"FinMind {dataset}: {raw.get('msg',raw.get('status'))}")
            return raw.get('data',[])
        except Exception as e:
            last=e;time.sleep(2**attempt)
    raise RuntimeError(str(last))

def finite(v):
    try:
        f=float(str(v).replace(',',''))
        return f if math.isfinite(f) else None
    except (TypeError,ValueError):return None

def ma(vals,n):return round(sum(vals[-n:])/n,3) if len(vals)>=n else None

def rsi(vals,n=14):
    if len(vals)<n+1:return None
    diffs=[vals[i]-vals[i-1] for i in range(len(vals)-n,len(vals))]
    gain=sum(max(0,x) for x in diffs)/n;loss=sum(max(0,-x) for x in diffs)/n
    return round(100 if loss==0 else 100-100/(1+gain/loss),2)

def build_one(stock, today):
    result={'id':stock,'updated_at':None,'price':None,'financials':{},'monthly_revenue':None,'errors':[]}
    start=(today-dt.timedelta(days=440)).isoformat()
    try:
        prices=fetch('TaiwanStockPrice',stock,start)
        cleaned=[]
        for p in prices:
            close=finite(p.get('close'))
            if close is not None and close>0:cleaned.append({'date':p['date'],'close':close,'volume':finite(p.get('Trading_Volume'))})
        cleaned.sort(key=lambda x:x['date']);cleaned=cleaned[-270:]
        if not cleaned:raise ValueError('無可用股價資料')
        vals=[x['close'] for x in cleaned]
        result['price']={'latest':cleaned[-1],'history':cleaned,'ma20':ma(vals,20),'ma60':ma(vals,60),'rsi14':rsi(vals)}
        result['updated_at']=cleaned[-1]['date']
    except Exception as e:result['errors'].append('股價：'+str(e)[:180])
    try:
        rows=fetch('TaiwanStockFinancialStatements',stock,(today-dt.timedelta(days=1100)).isoformat())
        eps=[]
        for x in rows:
            typ=str(x.get('type','')).strip().lower()
            if typ in ('eps','每股盈餘','earningspershare'):
                v=finite(x.get('value'))
                if v is not None:eps.append({'date':x.get('date'),'value':v})
        eps.sort(key=lambda x:x['date'] or '')
        # Financial dataset conventions can differ; show EPS as source data, never assume TTM without validated quarters.
        result['financials']={'eps_records':eps[-12:],'note':'EPS 原始紀錄；不自動假設為近四季 EPS。請核對季別與累計口徑。'}
    except Exception as e:result['errors'].append('財報：'+str(e)[:180])
    try:
        rows=fetch('TaiwanStockMonthRevenue',stock,(today-dt.timedelta(days=500)).isoformat())
        clean=[]
        for x in rows:
            v=finite(x.get('revenue'))
            if v is not None:clean.append({'date':x.get('date'),'revenue':v})
        clean.sort(key=lambda x:x['date'] or '')
        result['monthly_revenue']=clean[-15:]
    except Exception as e:result['errors'].append('月營收：'+str(e)[:180])
    return result

def main():
    config=json.loads((ROOT/'stocks.json').read_text(encoding='utf-8'))
    today=dt.date.today();items=[]
    for stock in config['stocks']:
        if not (stock.isdigit() and len(stock) in (4,5,6)):raise ValueError('Invalid stock code: '+stock)
        print('Fetching',stock,flush=True)
        items.append(build_one(stock,today))
        time.sleep(float(os.getenv('REQUEST_PAUSE','0.8')))
    snapshot={'schema_version':1,'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'provider':'FinMind API v4','provider_url':'https://finmind.github.io/','stocks':items,'disclaimer':'資料僅供研究，非投資建議。資料延遲、缺漏及錯誤均可能發生。'}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp');temp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(OUT)
    print('Wrote',OUT,'with',sum(bool(x['price']) for x in items),'price records')
    if not any(x['price'] for x in items):raise RuntimeError('No valid prices fetched: do not publish an empty snapshot')
if __name__=='__main__':main()
