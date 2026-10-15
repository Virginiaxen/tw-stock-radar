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

def revenue_analysis(records, today=None):
    """Monthly revenue diagnostics; only positive, unique month pairs yield YoY."""
    today = today or dt.date.today()
    by_month = {}
    warnings = []
    current_month_start = today.replace(day=1)
    for item in records:
        date = item.get('date')
        try:
            parsed_date = dt.date.fromisoformat(str(date)[:10])
            month = parsed_date.strftime('%Y-%m')
        except (TypeError, ValueError):
            warnings.append('月營收日期無效：' + str(date)[:30])
            continue
        if parsed_date >= current_month_start:
            warnings.append(f'{month} 尚未結束或屬未來月份，已排除，請核對 FinMind 日期定義')
            continue
        by_month.setdefault(month, []).append(item['revenue'])
        if item['revenue'] < 0:
            warnings.append(f'{month} 月營收為負數，請核對來源與會計口徑')
    for month, values in sorted(by_month.items()):
        if len(values) > 1:
            warnings.append(f'{month} 有 {len(values)} 筆月營收，避免重複計算')
    latest_month = max(by_month, default=None)
    result = {'latest_month': latest_month, 'latest_revenue': None,
              'prior_year_revenue': None, 'yoy_pct': None,
              'yoy_status': '無月營收資料', 'warnings': warnings}
    if latest_month is None:
        return result
    latest_values = by_month[latest_month]
    if len(latest_values) != 1:
        result['yoy_status'] = '最新月份有重複資料'
        return result
    current = latest_values[0]
    result['latest_revenue'] = current
    prior_month = f'{int(latest_month[:4])-1}{latest_month[4:]}'
    previous_values = by_month.get(prior_month, [])
    if not previous_values:
        result['yoy_status'] = '缺少去年同月資料'
    elif len(previous_values) != 1:
        result['yoy_status'] = '去年同月有重複資料'
    else:
        previous = previous_values[0]
        result['prior_year_revenue'] = previous
        if current < 0 or previous <= 0:
            result['yoy_status'] = '營收為負數或去年同月為零，暫不計算'
        else:
            result['yoy_pct'] = round((current / previous - 1) * 100, 2)
            result['yoy_status'] = '已計算'
    return result

def validate_eps(records, today=None):
    """Validate FinMind single-quarter EPS records; do not infer split-adjusted TTM."""
    today = today or dt.date.today()
    by_date = {}
    warnings = []
    for item in records:
        raw_date = item.get('date')
        value = finite(item.get('value'))
        try:
            d = dt.date.fromisoformat(str(raw_date)[:10])
        except (ValueError, TypeError):
            warnings.append(f'無效 EPS 財報日期：{str(raw_date)[:30]}')
            continue
        if (d.month, d.day) not in ((3, 31), (6, 30), (9, 30), (12, 31)):
            warnings.append(f'{d.isoformat()} 不是標準季度結束日')
            continue
        if d > today:
            warnings.append(f'{d.isoformat()} 是未來財報日期，已排除')
            continue
        if value is None:
            warnings.append(f'{d.isoformat()} EPS 非有效數字')
            continue
        by_date.setdefault(d, []).append(value)
    for d, values in sorted(by_date.items()):
        if len(values) != 1:
            warnings.append(f'{d.isoformat()} EPS 有 {len(values)} 筆，禁止重複計算')
    valid = sorted((d, vals[0]) for d, vals in by_date.items() if len(vals) == 1)
    latest = valid[-1][0] if valid else None
    recent = valid[-4:]
    consecutive = False
    if len(recent) == 4:
        def qindex(d):
            return d.year * 4 + (d.month // 3 - 1)
        consecutive = all(qindex(recent[i + 1][0]) - qindex(recent[i][0]) == 1 for i in range(3))
    if len(recent) < 4:
        status = '近四季 EPS 資料不足'
    elif not consecutive:
        status = '最近四筆 EPS 季度不連續'
    else:
        status = '季度連續，但未驗證配股與股票分割調整'
        warnings.append('FinMind 單季 EPS 可能因配股或分割跨季基準不一致，未驗證前不計算 TTM')
    return {
        'source': 'FinMind TaiwanStockFinancialStatements / EPS',
        'basis': '單季基本每股盈餘（依 FinMind 官方文件）',
        'latest_quarter': latest.isoformat() if latest else None,
        'quarter_count': len(valid),
        'last_four_consecutive': consecutive,
        'ttm_eps': None,
        'ttm_status': status,
        'warnings': warnings,
    }

def build_one(stock, today):
    result={'id':stock,'updated_at':None,'price':None,'financials':{},'monthly_revenue':None,'revenue_analysis':None,'errors':[]}
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
        result['financials']={'eps_records':eps[-12:],'eps_validation':validate_eps(eps,today),'note':'FinMind EPS 為單季值；未驗證配股／分割調整前，不提供 TTM EPS。'}
    except Exception as e:result['errors'].append('財報：'+str(e)[:180])
    try:
        rows=fetch('TaiwanStockMonthRevenue',stock,(today-dt.timedelta(days=500)).isoformat())
        clean=[]
        for x in rows:
            v=finite(x.get('revenue'))
            if v is not None:clean.append({'date':x.get('date'),'revenue':v})
        clean.sort(key=lambda x:x['date'] or '')
        # Only completed calendar months are eligible for public display.
        # This is a conservative date guard, not verification of the provider's month semantics.
        month_start=today.replace(day=1)
        eligible=[]
        for item in clean:
            try:
                if dt.date.fromisoformat(str(item['date'])[:10]) < month_start:
                    eligible.append(item)
            except (TypeError,ValueError):
                pass
        result['monthly_revenue']=eligible[-15:]
        result['revenue_analysis']=revenue_analysis(clean,today)
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
