"""Local-only annual profit calculation and respectful service-fit reminder."""
import argparse
import json
from pathlib import Path
from business_baseline import assess_service_fit, fit_summary, FIRST_QUESTION

def main():
    parser=argparse.ArgumentParser(description='本地核对年度利润；不联网、不上传、不自动拒单。无输入时仅显示首问。')
    parser.add_argument('--input',help='财务JSON文件。字段：entity, period, currency, unit, basis, income, gross, net, data_status, net_definition, informed_continuation。')
    parser.add_argument('--language',choices=['zh-CN','en'],default='zh-CN')
    parser.add_argument('--example',action='store_true',help='显示虚构输入格式，不把示例当客户事实。')
    args=parser.parse_args()
    if args.example:
        print(json.dumps({'entity':'虚构示例','period':'2025','currency':'CNY','unit':'万元','basis':'同一主体合并年度财务','income':1000,'gross':300,'net':30,'net_definition':'after_tax_consolidated','data_status':'actual','source_type':'user_report','informed_continuation':False},ensure_ascii=False,indent=2))
        return
    if not args.input:
        print('What were your annual gross profit and net profit?' if args.language=='en' else FIRST_QUESTION)
        print('Include revenue for the same full year, entity, year, currency and unit; unknown is acceptable.' if args.language=='en' else '请补同一主体、同一完整年度营业收入、年份、币种和单位；不知道可以直接说不知道。')
        return
    payload=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    result=assess_service_fit(payload.get('financial_intake',payload) if isinstance(payload,dict) else payload)
    result['user_message']=fit_summary(result,en=args.language=='en')
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':main()
