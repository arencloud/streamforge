#!/usr/bin/env python3
"""Run against the credential-free preview at localhost:8088 only."""
import json
import time
import urllib.request
import urllib.error
BASE='http://127.0.0.1:8088'
def call(path, method='GET', body=None, header=True):
    request=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json',**({'X-Streamforge-Action':'orders'} if header else {})})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)
status,data=call('/api/orders')
assert status==200 and data['preview'] is True, 'Never run preview mutation tests against a real database'
order_id=int(time.time()*1000)*100+17
path='/api/orders/'+str(order_id)+'/status'
status,order=call('/api/orders','POST',{'id':order_id,'customerName':'<script>synthetic</script>','amount':12.50});assert status==201
status,_=call('/api/orders','POST',{'id':order_id,'customerName':'Duplicate','amount':12.50});assert status==409
status,_=call(path,'PATCH',{'status':'shipped','expectedUpdatedAt':order['updatedAt']});assert status==400
status,_=call(path,'PATCH',{'status':'paid','expectedUpdatedAt':order['updatedAt']});assert status==200
status,_=call(path,'PATCH',{'status':'cancelled','expectedUpdatedAt':order['updatedAt']});assert status==409
status,_=call('/api/orders','POST',{'id':order_id+1,'customerName':'No header','amount':1},False);assert status==403
status,_=call('/api/orders','POST',{'id':order_id+1,'customerName':'Negative','amount':-1});assert status==400
status,_=call('/q/health/ready');assert status==200
print('Preview API: duplicates, transitions, stale writes, action header, invalid amount, readiness passed')
