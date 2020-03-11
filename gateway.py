import re
import sqlite3 as sqlite
import bitcoinrpc.authproxy as authproxy
import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.status import HTTP_401_UNAUTHORIZED
import secrets
import uvicorn
from starlette.requests import Request
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

app = FastAPI()
security = HTTPBasic()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

with open('config.json') as json_file:
    config = json.load(json_file)

instance = authproxy.AuthServiceProxy(config['other']['node'])

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, config["main"]["admin-username"])
    correct_password = secrets.compare_digest(credentials.password, config["main"]["admin-password"])
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/")
async def index(request: Request):
    heights = await getHeights()
    return templates.TemplateResponse("index.html", {"request": request, 
                                                     "chainName": config['main']['name'],
                                                     "assetID": config['tn']['assetId'],
                                                     "tn_gateway_fee":config['tn']['gateway_fee'],
                                                     "tn_network_fee":config['tn']['network_fee'],
                                                     "tn_total_fee":config['tn']['network_fee']+config['tn']['gateway_fee'],
                                                     "eth_gateway_fee":config['other']['gateway_fee'],
                                                     "eth_network_fee":config['other']['network_fee'],
                                                     "eth_total_fee":config['other']['network_fee'] + config['other']['gateway_fee'],
                                                     "fee": config['tn']['fee'],
                                                     "company": config['main']['company'],
                                                     "email": config['main']['contact-email'],
                                                     "telegram": config['main']['contact-telegram'],
                                                     "recovery_amount":config['main']['recovery_amount'],
                                                     "recovery_fee":config['main']['recovery_fee'],
                                                     "ethHeight": heights['Other'],
                                                     "tnHeight": heights['TN'],
                                                     "tnAddress": config['tn']['gatewayAddress'],
                                                     "ethAddress": config['other']['gatewayAddress']})

@app.get('/heights')
async def getHeights():
    dbCon = sqlite.connect('gateway.db')
    result = dbCon.cursor().execute('SELECT chain, height FROM heights WHERE chain = "Other" or chain = "TN"').fetchall()
    return { result[0][0]: result[0][1], result[1][0]: result[1][1] }

@app.get('/errors')
async def getErrors(request: Request, username: str = Depends(get_current_username)):
    if (config["main"]["admin-username"] == "admin" and config["main"]["admin-password"] == "admin"):
        return {"message": "change the default username and password please!"}
    
    if username == config["main"]["admin-username"]:
        dbCon = sqlite.connect('gateway.db')
        result = dbCon.cursor().execute('SELECT * FROM errors').fetchall()
        return templates.TemplateResponse("errors.html", {"request": request, "errors": result})

@app.get('/executed')
async def getErrors(request: Request, username: str = Depends(get_current_username)):
    if (config["main"]["admin-username"] == "admin" and config["main"]["admin-password"] == "admin"):
        return {"message": "change the default username and password please!"}
    
    if username == config["main"]["admin-username"]:
        dbCon = sqlite.connect('gateway.db')
        result = dbCon.cursor().execute('SELECT * FROM executed').fetchall()
        return templates.TemplateResponse("tx.html", {"request": request, "txs": result})

@app.get('/ethAddress/{address}')
async def checkTunnel(address):
    dbCon = sqlite.connect('gateway.db')
    address = re.sub('[\W_]+', '', address)
    values = (address,)

    result = dbCon.cursor().execute('SELECT targetAddress FROM tunnel WHERE sourceAddress = ?', values).fetchall()
    if len(result) == 0:
        targetAddress = None
    else:
        targetAddress = result[0][0]

    return { 'sourceAddress': address, 'targetAddress': targetAddress }

@app.get('/tunnel/{sourceAddress}/{targetAddress}')
async def createTunnel(sourceAddress, targetAddress):
    dbCon = sqlite.connect('gateway.db')
    sourceAddress = re.sub('[\W_]+', '', sourceAddress)
    targetAddress = re.sub('[\W_]+', '', targetAddress)
    values = (sourceAddress, targetAddress)

    result = dbCon.cursor().execute('SELECT targetAddress FROM tunnel WHERE sourceAddress = ?', (sourceAddress,)).fetchall()
    if len(result) == 0:
        valAddress = instance.validateaddress(sourceAddress)
        if valAddress['isvalid']:
            dbCon.cursor().execute('INSERT INTO TUNNEL ("sourceAddress", "targetAddress") VALUES (?, ?)', values)
            dbCon.commit()

            return { 'successful': True }
        else:
            return { 'successful': False }    
    else:
        return { 'successful': False }    