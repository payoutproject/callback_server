from requests import request
import json
from collections import OrderedDict
import hashlib
from libs.utils.mytime import UtilTime
from utils.exceptions import PubErrorCustom
from apps.order.models import Order
from apps.paycall.utils import PayCallLastPass
from apps.utils import url_join
import time
from libs.utils.log import logger
import demjson

from Crypto.Cipher import AES
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA,SHA256
from apps.pay.models import PayPass

import base64

class LastPassBase(object):

    def __init__(self,**kwargs):
        self.secret = kwargs.get('secret')
        self.data = kwargs.get('data',{})

    def _sign(self):
        pass


    def call_run(self,request):

        callback_ip = request.META.get("HTTP_X_REAL_IP")

        logger.info("回调IP：{}".format(callback_ip))

        payObj = PayPass.objects.filter(callback_ip__contains=callback_ip)
        payObjTmp=None
        if payObj.exists():
            for item in payObj:
                print(item.callback_ip)
                for itemtmp in item.callback_ip.split(","):
                    print(itemtmp)
                    if str(itemtmp).strip() == str(callback_ip).strip():
                        payObjTmp = item
                        break
                if payObjTmp:
                    break
        else:
            raise PubErrorCustom("拒绝访问")

        if not payObjTmp:
            raise PubErrorCustom("拒绝访问")
        payObj = payObjTmp

        rules = json.loads(payObj.rules)

        logger.info("规则：{}".format(rules["callback"]))
        logger.info("回调数据：{}".format(self.data))

        if str(self.data.get(rules["callback"]["codeKey"])) == rules["callback"]["ok"]:
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get(rules["callback"]["key"]))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

            return rules["callback"]["rvalue"]

        return "error"


class LastPass_JLF(LastPassBase):

    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #测试环境
        # self.create_order_url = "http://pre.api.otcbank.net/pay/createPayOrder"
        # self.secret = "89d50bea1f06406abaf73997a822ecd6"
        # self.businessId = "10012"

        #生产环境
        self.create_order_url="http://api.otcbank.net/pay/createPayOrder"
        self.secret = "7f9b8d71340441d89f4ab8523b0f9a79"
        self.businessId = "10015"

        self.response = None

    def _sign(self):

        valid_data={}
        #去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        valid_data['secret'] = self.secret

        #排序固定位置
        valid_data_keys=sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        #将数据变成待加密串
        encrypted=str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['sign']=hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response =  json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('businessId',int(self.businessId))
        self.data.setdefault('signType','MD5')
        self.data.setdefault('payTitle','商品1')
        self.data.setdefault('random',UtilTime().timestamp)
        self.data.setdefault('payMethod',0)
        self.data.setdefault('dataType',0)
        # self.data.setdefault('returnUrl',url_join("/pay/#/juli"))
        self._sign()
        try:
            self._request()
            return (False, self.response['errorDesc']) if not self.response['successed'] else (True,self.response['returnValue'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("businessId") or self.data.get("businessId")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("signType") or self.data.get("signType")!= 'MD5':
            raise PubErrorCustom("签名类型不正确")
        if not self.data.get("outTradeNo"):
            raise PubErrorCustom("商户订单号为空!")
        if not self.data.get("orderState"):
            raise PubErrorCustom("订单状态为空!")

        if self.data.get("orderState") == 'success':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("outTradeNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_TY(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://pay.dingyizf.com/api/pay/create_order"
        self.secret = "1TBFPYISMBBNW4LALBZH6DC6UPOQJSOQ5PIZTPWUEEGGEUHB2IIUKGSRGEKZAHR2FAINUUMKRERRAR8DCL2DFORYXQGLYVNF2TVHVH6XVHZSKU4E7M2PG2GOCTB8OZJT"
        self.businessId = 20000003

        self.appId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        # self.productId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('mchId',self.businessId)
        self.data.setdefault('appId',self.appId)


        self.data.setdefault('currency','cny')

        # self.data.setdefault('productId', self.productId)
        self.data.setdefault('subject','商品P')
        self.data.setdefault('body', '商品P6666')

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()


        try:
            self._request()
            print(self.response)
            return (False, self.response['retMsg']) if self.response['retCode']!='SUCCESS' else (True,self.response['payParams']['payUrl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("mchOrderNo"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["amount"] = float(self.data.get("amount")) / 100.0

        if str(self.data.get("status")) == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("mchOrderNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_YZL(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://39.109.0.189/PayOrder/payorder"
        self.secret = "nMuNRjQd8hEFFX4u8JNCBNM6pEn35PdW"
        self.businessId = "658431973136167"
        self.businessNo = "048628"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted[:-1]+self.secret).encode("utf-8")
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        encrypted = (str(self.data['out_order_no'])+str(self.data['total_fee'])+str(self.data['trade_status'])+str(self.businessId)+str(self.secret)).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        print(self.data['sign'])
        print(sign)
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):

        self.data.setdefault('subject',"商品M")
        self.data.setdefault('body','商品MM')
        self.data.setdefault('return_url', url_join("/pay/#/juli"))
        self.data.setdefault('partner', self.businessId)
        self.data.setdefault('user_seller', self.businessNo)
        self._sign()

        self.data.setdefault('pay_type',"zfbh5")
        self.data.setdefault('http_referer', "allwin6666.com")

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        if not self.data.get("total_fee") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("out_order_no"):
            raise PubErrorCustom("商户订单号为空!")
        self.check_sign()

        if self.data.get("trade_status") == 'TRADE_SUCCESS':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("out_order_no"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)


class LastPass_DD(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://zf.da12.cc/Pay_Index.html"
        self.secret = "785g5ykawr9jkzgw9qpkh562w5dhvsfp"
        self.businessId = "190649615"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_OSB(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.yitengkeji.top/index/api/order"
        self.secret = "5ab569e8ed79c369e76fb1e4b02f7b8131fa4ce96ba0a37b4fb21022a493b1c6"
        self.businessId = "69659de1f6b175d0663ec453f648677f"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}{}".format(item, valid_orders_data[item])
        encrypted = (self.secret+encrypted+self.secret).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response=json.loads(result.content.decode('utf-8'))
        print(self.response)

    def run(self):

        self.data.setdefault('client_id',self.businessId)
        self.data.setdefault('timestamp',UtilTime().timestamp*1000)
        self._sign()

        try:
            self._request()
            return (False, self.response['msg']) if self.response['code'] != 200 else (True,self.response['data'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("total") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("api_order_sn"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("callbacks") == 'CODE_SUCCESS':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("api_order_sn"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_BAOZHUANKA(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.gudad.cn/pay/acp"
        self.secret = "67eh6aatf8megjz4pkoob4d7cohxzew8"
        self.businessId = "23"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text
        print(self.response)
    def run(self):
        self.data.setdefault('u',self.businessId)

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()

        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_LIMAFU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://api.ponypay1.com/"
        self.secret = "1359859484107426286869760710762572181072460749407628796928543285"
        self.businessId = "95560"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):

        parastring=(self.data['merchant_id'] + self.data['orderid']+self.data['money']+self.secret).encode("gb2312")

        sign = hashlib.md5(parastring).hexdigest()

        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))
    def run(self):

        self.data.setdefault('merchant_id',self.businessId)
        self.data.setdefault('paytype','YSF')
        self.data.setdefault('callbackurl','http://www.baidu.com')

        parastring = (self.data['merchant_id']+self.data['orderid']+self.data['paytype']+self.data['notifyurl']+self.data['callbackurl']+self.data['money']+self.secret).encode("gb2312")
        self.data['sign'] = hashlib.md5(parastring).hexdigest()


        try:
            self._request()
            print(self.response)
            return (False, self.response['message']) if self.response['status']!='1' else (True,self.response['data'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("money") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("status") == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_JUXING(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://118.31.8.186:3020/api/pay/create_order"
        self.secret = "QRG0S1WNGWNPIGCU6UEFBTHXAIR7YL4VTEIWRIBZKZPFD9FLTGE84CFLJWFYYVEPJRMRJJIGE4NPM6YIVZETDFAUCBEPTS7NRFPMUMOJRWTSICWZK5SOP8CUDBSQJC51"
        self.businessId = 20000041
        self.appId='1a3e473671434f06a06a31ab1f6dad13'
        self.productId=8023

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('mchId',self.businessId)
        self.data.setdefault('appId',self.appId)


        self.data.setdefault('currency','cny')

        self.data.setdefault('productId', self.productId)
        self.data.setdefault('subject','商品P')
        self.data.setdefault('body', '商品P6666')

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()


        try:
            self._request()
            print(self.response)
            return (False, self.response['retMsg']) if self.response['retCode']!='SUCCESS' else (True,self.response['payParams']['payUrl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("mchOrderNo"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["amount"] = float(self.data.get("amount")) / 100.0

        if str(self.data.get("status")) == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("mchOrderNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_MK(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.lianermei.cn/Pay_Index.html"
        self.secret = "2pztqmsktehj76exsw1c9sjjtd4lfqmi"
        self.businessId = "10213"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)

        self.response = result.text
        logger.info(self.response)

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        # self.data.setdefault('pay_bankcode',"904")
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        self.data.setdefault('create_order_url',self.create_order_url)

        return self.data

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_TONGYU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://8oep1k.apolo-pay.com/unifiedorder"
        self.secret = "ed0556b7d7414ab3bef6dac7ac69b47a"
        self.businessId = "10000044"

        self.response = None

        self.signature =None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # 将数据变成待加密串
        encrypted = ("biz_content={}&key={}".format(demjson.encode(valid_orders_data), self.secret)).encode("utf-8")
        self.signature = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self,sign):
        self._sign()
        if self.signature != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self,data):
        result = request(method='POST', url=self.create_order_url, params=data, verify=True)
        self.response =  json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('mch_id',self.businessId)
        self.data.setdefault('pay_platform','WXPAY')
        self.data.setdefault('pay_type','MWEB')
        self.data.setdefault('cur_type','CNY')
        self.data.setdefault('body','夏季服装')


        self._sign()

        data={
            "sign_type":"MD5",
            "signature" : self.signature,
            "biz_content" : demjson.encode(self.data)
        }

        try:
            self._request(data)
            return (False, self.response['ret_msg']) if str(self.response['ret_code'])!='0' else (True,self.response['biz_content']['mweb_url'])
        except Exception as e:
            return (False,str(e))


    def call_run(self):

        status =str(self.data.get("ret_code"))
        signature = self.data.pop('signature',False)

        self.data = self.data.get("biz_content")

        self.check_sign(signature)

        # self.data["payment_fee"] = float(self.data.get("payment_fee")) / 100.0

        if not self.data.get("mch_id") or self.data.get("mch_id")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("payment_fee") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("out_order_no"):
            raise PubErrorCustom("商户订单号为空!")

        if status == '0':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("out_order_no"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_JIAE(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #生产环境
        self.create_order_url="http://47.106.72.35:8880/Pay"
        self.secret = "IhJfRzVUgCjXronbudHepSbYtRbOtflA"
        self.businessId = "2019117"

        self.response = None
        self.signature =None

    def _request(self):
        result = request(method='POST', url=self.create_order_url, params=self.data, verify=True)
        self.response =  json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('fxid',self.businessId)
        self.data.setdefault('fxdesc','夏季服装')


        # self.data.setdefault('fxddh','fdsa1')
        # self.data.setdefault('fxfee','100')
        # self.data.setdefault('fxnotifyurl','http://www.baidu.com')
        # self.data.setdefault('fxbackurl','http://www.baidu.com')
        self.data.setdefault('fxpay','pddjx')
        # self.data.setdefault('fxip','192.168.0.1')

        encrypted = (str(self.data['fxid']) + str(self.data['fxddh']) + str(self.data['fxfee']) + str(self.data['fxnotifyurl']) + self.secret).encode("utf-8")
        self.data['fxsign'] = hashlib.md5(encrypted).hexdigest()

        try:
            self._request()
            return (False, self.response['error']) if str(self.response['status'])!='1' else (True,self.response['payurl'])
        except Exception as e:
            return (False,str(e))


    def call_run(self):

        encrypted = (str(self.data['fxstatus']) + str(self.data['fxid']) + str(self.data['fxshddh']) + str(self.data['fxfee']) + self.secret).encode("utf-8")

        sign = hashlib.md5(encrypted).hexdigest()
        if self.data['fxsign'] != sign:
            raise PubErrorCustom("验签失败!")

        if not self.data.get("fxid") or self.data.get("fxid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("fxfee") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("fxshddh"):
            raise PubErrorCustom("商户订单号为空!")

        if str(self.data.get("fxstatus")) == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("fxshddh"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_DONGFANG(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.dongfangguo.cn/PayOrder/payorder"
        self.secret = "Ms7niYe7mTjUtbR7CMBiwgDXnfEBFJbH"
        self.businessId = "293814614667811"
        self.businessNo = "635029"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted[:-1]+self.secret).encode("utf-8")
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        encrypted = (str(self.data['out_order_no'])+str(self.data['total_fee'])+str(self.data['trade_status'])+str(self.businessId)+str(self.secret)).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        print(self.data['sign'])
        print(sign)
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):

        self.data.setdefault('subject',"商品M")
        self.data.setdefault('body','商品MM')
        self.data.setdefault('return_url', url_join("/pay/#/juli"))
        self.data.setdefault('partner', self.businessId)
        self.data.setdefault('user_seller', self.businessNo)
        self._sign()

        self.data.setdefault('pay_type',"wx")
        # self.data.setdefault('http_referer', "allwin6666.com")

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        if not self.data.get("total_fee") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("out_order_no"):
            raise PubErrorCustom("商户订单号为空!")
        self.check_sign()

        if self.data.get("trade_status") == 'TRADE_SUCCESS':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("out_order_no"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)


class LastPass_XIONGMAO(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #生产环境
        self.create_order_url="http://47.244.25.42/Handler/sdk.ashx?type=create_newpay"
        self.secret = "WrSffkKaQ5EIGPSjIN+jpqkRrjnZ2heQ/3Ra0q1IAvs="
        self.businessId = 'M019'

        # self.appId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        # self.productId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].upper().encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('app_id',self.businessId)


        self.data.setdefault('time',UtilTime().timestamp)
        self.data.setdefault('mark',"mark")

        self._sign()

        try:
            self._request()
            print(self.response)
            return (False, self.response['Message']) if str(self.response['Status'])!='1' else (True,self.response['Result']['payurl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("price") :
            raise PubErrorCustom("金额不能为空!")

        if str(self.data.get("msg")) == '支付成功':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("order_id"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_KUAILAI(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #生产环境
        self.create_order_url="http://59.56.76.24:8080/pay-api/pay/createOrder"
        self.secret = "d5dbe1c4ebd44805919d5c9e044437b3"
        self.response_secret = '8f8390ad665147eeb4b3d4aefb786c2e'
        self.businessId = '107'

        # self.appId = '98c51ce4ac6f44d5aed38892d5bd09d1'
        #
        # self.productId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        self.response = None

    def _sign(self,secret):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted[:-1]+'&'+secret).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign(self.response_secret)
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('umId',self.businessId)
        self.data.setdefault('payType',"ALI_SCAN")

        self.data.setdefault('subject',"subject")
        self.data.setdefault('body',"body")
        self.data.setdefault('backParams',"backParams")

        self._sign(self.secret)


        try:
            self._request()
            print(self.response)
            return (False, self.response['msg']) if str(self.response['code'])!='0' else (True,self.response['data']['html'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("umNo"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["amount"] = float(self.data.get("amount")) / 100.0

        if str(self.data.get("status")) == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("umNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_SHANGHU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://api.pfal.cn/apis.php"
        self.secret = "54F1HM9ZTIEM26QIAIWQKK6U1J9PP56M"
        self.businessId = 'bae012'

        # self.appId = '98c51ce4ac6f44d5aed38892d5bd09d1'
        #
        # self.productId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        self.response = None

    # def check_sign(self):
    #     sign = self.data.pop('sign',False)
    #     self._sign()
    #     if self.data['sign'] != sign:
    #         raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('shid',self.businessId)
        self.data.setdefault('key',self.secret)
        self.data.setdefault('pay',"wx")
        self.data.setdefault('url',"http://api.pfal.cn/success.php")
        self.data.setdefault('create_order_url',self.create_order_url)

        return self.data

    def call_run(self):

        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("shid"):
            raise PubErrorCustom("商户订单号为空!")

        tmp = str(hashlib.md5('54F1HM9ZTIEM26QIAIWQKK6U1J9PP56M'.encode("utf-8")).hexdigest()).encode(
            'utf-8') + 'bae012'.encode("utf-8")

        sign = hashlib.md5(tmp).hexdigest()
        print(sign)
        if self.data.get('shkey') != sign:
            raise PubErrorCustom("签名错误!")

        if str(self.data.get("status")) == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_HAOYUN(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://118.31.8.186:3020/api/pay/create_order"
        self.secret = "RQSSRGEUBGPPGZ414KEFISF3FU8FIKLB6XT7WDMCYUQFRP2WHJD0GJP7PRYW0QHEBDQZ9V8ZZ0X25VEUSYAJWBBH5QTNVMXRPZHWODHNBHBWXYUAYRHLXKISUYQA81S9"
        self.businessId = 20000001
        self.appId='fede1f578220403680fc97bc704cbf65'
        self.productId=8019

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('mchId',self.businessId)
        self.data.setdefault('appId',self.appId)


        self.data.setdefault('currency','cny')

        self.data.setdefault('productId', self.productId)
        self.data.setdefault('subject','商品P')
        self.data.setdefault('body', '商品P6666')

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()


        try:
            self._request()
            print(self.response)
            return (False, self.response['retMsg']) if self.response['retCode']!='SUCCESS' else (True,self.response['payParams']['payUrl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("mchOrderNo"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["amount"] = float(self.data.get("amount")) / 100.0

        if str(self.data.get("status")) == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("mchOrderNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_FENGNIAO(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #生产环境
        self.create_order_url="http://47.52.226.57:8313/x1/pay/order"

        self.secret = "edfe2d4cba904d4299e3a7f56ee6c8f9"
        self.businessId = '88882019070910000003'
        self.appId='ef4dfb8a19ba459eb71edddee325cd29'
        self.productId=8019

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}".format(valid_orders_data[item])
        encrypted = encrypted.encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('merchantNo',self.businessId)
        self.data.setdefault('appid',self.appId)
        self.data.setdefault('version','1.0')
        self.data.setdefault('payChannel','01')
        self.data.setdefault('payType','01')

        self.data.setdefault('tradeTime',UtilTime().arrow_to_string(format_v='YYYYMMDDHHmmss'))
        self.data.setdefault('productName', '商品P6666')

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()


        try:
            self._request()
            print(self.response)
            return (False, self.response['resultMsg']) if self.response['resultCode']!='000000' else (True,self.response['payInfo'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("merchantOrderNo"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["amount"] = float(self.data.get("amount")) / 100.0

        if str(self.data.get("status")) == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("merchantOrderNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_LIANJINHAI(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://47.75.163.84/pay-api/unified/pay"

        self.secret = "fnxrsc8nd2pfm6esesqed9rsy17w7qla"
        self.businessId = '5010661907102124136792'
        self.appId='10051907102124530961'
        self.productId=8019

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, json=self.data,verify=True,headers={
            "Content-Type":'application/json'
        })
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('mch_no',self.businessId)
        self.data.setdefault('app_id',self.appId)


        self.data.setdefault('nonce_str',str(UtilTime().timestamp))

        self.data.setdefault('trade_type', 'ALI_H5')
        self.data.setdefault('body', '商品P6666')

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()

        try:
            self._request()
            print("上游返回参数:{}".format(self.response))
            return (True,self.response['pay_info']) if 'return_code' in self.response and self.response['return_code'] == '0000' else (False, self.response['return_msg'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("total_fee") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("out_trade_no"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["total_fee"] = float(self.data.get("total_fee")) / 100.0

        ordercode = self.data.get("out_trade_no")

        ordercode = ordercode.replace('ALLWIN8888','')
        print(ordercode)

        if str(self.data.get("return_code")) == '0000':
            try:
                order = Order.objects.select_for_update().get(ordercode=ordercode)
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_JIUFU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        # self.create_order_url="http://yuwhjh.club"
        # self.secret = "q66mo5xugzxv4amd2fw6e2t1jsdyvujy"
        # self.businessId = "190729763"
        # self.bankcode = "926"

        #玖玖
        self.create_order_url="http://47.89.13.174:82/Pay_Index.html"
        self.secret = "amsxng3iwpo73bzezyp0rm7ze5qiywd3"
        self.businessId = "10632"
        self.bankcode = "904"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)

        self.response = result.text
        logger.info(self.response)

    def run(self):

        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        # self.data.setdefault('pay_bankcode',"904")
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        self.data.setdefault('create_order_url',self.create_order_url)

        return self.data

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_XINGYUANFU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://pay.49y1e.cn/PayBank.aspx"

        self.secret = "d058d3b8a25d49a6a3df898bcba4889b"
        self.businessId = 1748
        self.response = None

    def _request(self):
        print(self.data)
        result = request(method='GET', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('partner',self.businessId)
        # self.data.setdefault('type',"8057")

        encrypted = "partner={}&type={}&value={}&orderid={}&callbackurl={}{}".format(
                            self.data.get('partner'),
                            self.data.get('type'),
                            self.data.get('value'),
                            self.data.get('orderid'),
                            self.data.get('callbackurl'),
                            self.secret)

        encrypted = encrypted.encode("utf-8")
        print(encrypted)
        self.data.setdefault('sign',hashlib.md5(encrypted).hexdigest())

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        encrypted = "partner={}&orderid={}&opstate={}&ovalue={}{}".format(
                            self.data.get('partner'),
                            self.data.get('orderid'),
                            self.data.get('opstate'),
                            self.data.get('ovalue'),
                            self.secret)

        encrypted = encrypted.encode("utf-8")
        print(encrypted)
        sign = hashlib.md5(encrypted).hexdigest()

        if sign != self.data.get('sign'):
            raise PubErrorCustom("签名错误!")

        if not self.data.get("ovalue") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("partner"):
            raise PubErrorCustom("商户订单号为空!")

        if str(self.data.get("opstate")) == '0':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_CHUANGYUAN(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://118.31.55.149:9880/index.php/refres/createorder/createdPddOrder"

        self.secret = "6914361d625640c30ba1e1d7d792ca05"
        self.businessId = "786761"
        self.lastId = '213791'
        self.appId='fede1f578220403680fc97bc704cbf65'
        self.productId=8019

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # valid_orders_data['key']=self.secret

        # 将数据变成待加密串

        valid_orders_data = demjson.encode(valid_orders_data)
        # print(valid_orders_data)
        # encrypted = dict()
        # for item in valid_orders_data:
        #     encrypted[item] = valid_orders_data[item]
        encrypted = valid_orders_data + self.secret
        print(encrypted)
        encrypted = encrypted.encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        signType = self.data.pop('signType',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))
        print(self.response)
        # self.data = self.response
        # self.check_sign()

    def run(self):


        self.data.setdefault('payType' , '9')
        self.data.setdefault('payObjet','1')
        self.data.setdefault('payMode','2')


        self.data.setdefault('partnerID',self.businessId)
        self.data.setdefault('institutionID',self.lastId)

        self._sign()

        self.data.setdefault('signType','MD')


        try:
            self._request()
            print(self.response)
            return (False, self.response['message']) if str(self.response['code'])!='200' else (True,self.response['paymentUrl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        print(self.data)
        self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("outordersn"):
            raise PubErrorCustom("商户订单号为空!")

        if str(self.data.get("code")) == '200':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("outordersn"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_WXHFYS(LastPassBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.create_order_url = "https://120.78.167.47/sywmPay"
        #私钥
        self.secret = "MIICXAIBAAKBgQC8e66qW8QPdU+7R7hb22vsJOO8LdF3IW+P9DbxUIajlElGYJGZXLr8e7sYW5wRQmQHEjEldMXD3o0dHn6C8y+pCtaPlcJi3cBFtQI63f1CCSM+ulTKLHBwj55v4uqCi2GeV3p6AFM1Y6JcR+hFVTp0TTAFis4tSUpZwpOc+F0axwIDAQABAoGAOpBHfiFTMuZlZrBrJQdxagcwR4kI+3YFHvpnk+VMYEkz100sEDXS155uTKwyOt6hC91oLdYxmKFuwSx3bKK5HMkSpi9yBDjx5NzmiJc173eQx4tu75GxWDCeCJpqKS7WCR9ArfKK9vbbrAqlBrOiwxpEPAj15J63iWrbFGM38kECQQDuAOF9VLJzNzo1dFDTJzvgU75tj13nQu0c5vtRSQWoWBpkRMFW037VwlKobl4F9ZSkWvh3RDK2wo+0jhp2njshAkEAyrw4CEIx3mIZjl8doLK2v97WYGCPJi1APVivqdJsJCgNi4UcIKfccqlm1sqVzFcbKVy/XhDN5aQJVh1bAJ3A5wJAcYM4CIeRyMPJXl9IgTzQIPCv/R8IoVjZMBS2PpF+Qkkq5TGpqJicgKT6uVxSObNkHnNI19FOAr6OvYWc94AGIQJAF8hMqmtZfkTzyofN6fQNDCUP8O5i3I+iYY/ty3YryXIJZLyQuCP48Fp+/eN1/yqYvRlsOZSvEqlTjw6Shlf7MQJBALKhHJrqmli+ndjljCIP6BvrGZSNGPgr8+JeyudI3rXu6t7NNN2Nif8l5XCUk9gYeX2oN5QvJeV0AFnth1nTWyQ="
        #self.secret = "MIICeAIBADANBgkqhkiG9w0BAQEFAASCAmIwggJeAgEAAoGBALwNXPM8FUpJR2taYG8ctrQFxckYfPdWPFfCqb7a2SIJ8O/tqk16SqfyvJeQUy9dzkd5AWfE933Bn7sgNBsfNc6b0PXQ0cyyhYvNRhegN3ZDZO/i+pKjblCpFZCkYGAEGwy05ubV8sEViQqT1st1geaZ48ugzyfWM9+6hp1oMfipAgMBAAECgYEAoDC19FFDRZOkrhM/wIbyL+oW8NXWZg9kudGOLZFZk8BqKMgI4ZUCEY0aD/YWlmvPM10l0FKeDNcqjQnCuTPd7ZqVKGzKYPljn3tEafv7/LLyRSsUFyS3CKDMVb+pVGtmAePInx7SxosaxY8Xa//e21Y0Job0ecyVGvgku3nyEwECQQDpPYmp0KeiUMSkY/HxP90cEcA2OANMRuhyFq6056KtUQEml5Q/j2fNduZ0z3PB84RfKc9p2Gr0Q4Y+KYFBOC2JAkEAzmcAdI/A1kc3nNzb3giq06kxcE6SJKSOOcByel1GrvRa5+7WaX7erCU7g1DTieM2MGbvzjvAjQAVtHlzYFbKIQJBAKxCKLPkSIpWgISw0/VLJ3AdpAnnIHhrPi1Ulz9AfCLo2qK3/GNc9FsI33eR53ps8WyfInKXxZYVcMXkPXP/m5ECQDHtbonDoET1EznJnxHVjOUIX2IoT2e3uoOzzr1UxN1bVIYYGxuHyftgQkYgjhsjsB8DN2zuvUQeSiHO4x7hv6ECQQCRxh9YVwzyPXkl5NJGDAQWuLf5EtSrB9gW7nLIJL8Geoww/yNi0YmmP4xFX7qJI6/eENGFI/6EKcLV9v/2VdZp"
        self.secret = "-----BEGIN RSA PRIVATE KEY-----\n" + self.secret + "\n-----END RSA PRIVATE KEY-----"
        #公钥
        self.public_secret = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCfRRqiTyiDRvgPwAnHm+odB6kEY1O51Zh5rlr3iSYEgDKfO00yD6ZCAh6MlKfYT0DD+WKN91lt6t9g/u0Cw2WJwGeUiOEWUDso/MiOGmdGYrfsarEzGCTSRmu1tIdwFKNi9HThcMTs7aU99lBtoGIYu2mxsXoWnLbdExZ9TaOBgwIDAQAB"
        #self.public_secret = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC8e66qW8QPdU+7R7hb22vsJOO8LdF3IW+P9DbxUIajlElGYJGZXLr8e7sYW5wRQmQHEjEldMXD3o0dHn6C8y+pCtaPlcJi3cBFtQI63f1CCSM+ulTKLHBwj55v4uqCi2GeV3p6AFM1Y6JcR+hFVTp0TTAFis4tSUpZwpOc+F0axwIDAQAB"
        self.public_secret = "-----BEGIN PUBLIC KEY-----\n" + self.public_secret + "\n-----END PUBLIC KEY-----"
        #商户号
        self.businessId = "1015200000000144"
        #节点号
        self.nodeNo = "10150146"
        #AESKEY
        self.Aeskey = "pQeP92XPlMocsxZKokFbHg=="
        # self.Aeskey = "v3fotW5LXw5AED5QxRswBQ=="


        self.txnType = 'T20301'

        self.response = None

        self.sign = ""
        self.bizContext = ""

    def encrypt(self,content, key):

        length = 16
        pad = length - (len(content) % length)
        count = 0
        while True:
            count += 1
            content += chr(pad)
            if count == pad:
                break
        key = base64.b64decode(key)
        cipher = AES.new(key, AES.MODE_ECB)  # ECB模式

        return base64.b64encode(cipher.encrypt(str.encode(content)))


    def decrypt(self,content,key):

        key = base64.b64decode(key)
        content = base64.b64decode(content)
        cipher = AES.new(key, AES.MODE_ECB)

        res = cipher.decrypt(content)
        self.decrypt_data = res[0:-1*res[-1]]
        return json.loads(res[0:-1*res[-1]])

    def rsa_sign(self,message):
        encrypted = message.encode("utf-8")
        private_key = RSA.importKey(self.secret)

        cipher = PKCS1_v1_5.new(private_key)
        h=SHA.new(encrypted)
        signature = cipher.sign(h)
        return base64.b64encode(signature)

    def rsa_design(self,signature):
        encrypted = self.decrypt_data
        public_key = RSA.importKey(self.public_secret)
        hash_obj = SHA.new(encrypted)
        try:
            PKCS1_v1_5.new(public_key).verify(hash_obj, base64.b64decode(signature))
            return True
        except (ValueError, TypeError):
            return False

    def _sign(self):
        valid_orders_data = {}
        valid_orders_data['outTradeNo'] = self.data['outTradeNo']
        valid_orders_data['totalAmount'] = self.data['totalAmount']
        valid_orders_data['currency'] = self.data['currency']
        valid_orders_data['body'] = self.data['body']
        valid_orders_data['notifyUrl'] = self.data['notifyUrl']
        valid_orders_data['orgCreateIp'] = self.data['orgCreateIp']

        bizContextJson = json.dumps(valid_orders_data,ensure_ascii=False)

        self.sign = self.rsa_sign(bizContextJson)

        self.bizContext = self.encrypt(bizContextJson,self.Aeskey)

    def check_sign(self):

        self.response = self.decrypt(self.data['bizContext'], self.Aeskey)

        sign = self.data.pop('sign', False)
        if not self.rsa_design(sign):
            return (False,"验签失败")

    def _request(self):

        data={
            "version" : '1.0' ,
            'orgId' : self.businessId,
            'nodeId': self.nodeNo,
            'orderTime': UtilTime().arrow_to_string(format_v="YYYYMMDDHHmmss"),
            'txnType': self.txnType,
            'signType': 'RSA',
            'charset': 'UTF-8',
            'bizContext': self.bizContext,
            'sign' : self.sign
        }
        result = request(method='POST', url=self.create_order_url, data=data, verify=False)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):

        self.data.setdefault('currency','CNY')
        self.data.setdefault('tranType','JH021')
        self.data.setdefault('body','shangpinM')

        self._sign()

        try:
            self._request()
            if str(self.response['code']) != 'SUCCESS':
                return (False, self.response['msg'])
        except Exception as e:
            return (False, str(e))


        response = self.decrypt(self.response['bizContext'], self.Aeskey)

        if response['retMsg'] != '成功':
            return (False, response['retMsg'])

        sign = self.response['sign']
        if not self.rsa_design(sign):
            return (False,"签名失败")
        return (True, response['payUrl'])

    def call_run(self):

        print(self.data)
        self.check_sign()
        print(self.response)
        if not self.response.get("outTradeNo"):
            raise PubErrorCustom("商户订单号为空!")

        if str(self.response.get("retCode")) == 'RC0000':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.response.get("outTradeNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)


class LastPass_ZFBHFYS(LastPass_WXHFYS):

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.txnType = 'T20302'

class LastPass_SDGY(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.218muv.cn/Pay_Index.html"

        self.secret = "bidy3bdpy1uerc3r3lyd2x0cuv687eko"
        self.businessId = "10021"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))
        print(self.response)

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        try:
            self._request()
            print(self.response)
            return (False, self.response['status_info']) if str(self.response['status'])!='success' else (True,self.response['payurl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_JIABAO(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://www.r4a.cn/Pay_Index.html"
        self.secret = "kj49mp93d3k00ygal3ipuqejk9dmrpjz"
        self.businessId = "190826990"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        print(sign,self.data['pay_md5sign'])
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        # self.data.setdefault('pay_bankcode',"904")
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        self.data.setdefault('create_order_url',self.create_order_url)

        return self.data

    def call_run(self):
        self.check_sign()

        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")
            order.amount = self.data.get("amount")
            order.confirm_amount = self.data.get("amount")
            PayCallLastPass().run(order=order)

class LastPass_QIANWANG(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.qwjpay.com/api/paygate/new"

        # self.create_order_url="http://requestbin.net/r/1crsgiq1"
        self.secret = "37a054c389b02d971bdfe7b13277da4a96252f67caa0fca7"
        self.businessId = "1022bbbc29843dc5"

        self.response = None

    def _request(self):

        result = request(method='POST', url=self.create_order_url, json=self.data,headers={
            "Content-Type":'application/json'
        })
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('merch_id',self.businessId)
        self.data.setdefault('qrtype','alipay-h5')
        self.data.setdefault('jump_url',url_join("/pay/#/juli"))
        self.data.setdefault('title','会员充值')

        encrypted = "merch_id={}&merch_order_id={}&key={}".format(
            self.data.get("merch_id"),
            self.data.get("merch_order_id"),
            self.secret).encode("utf-8")

        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

        try:
            self._request()
            print(self.response)
            return (False, self.response['message']) if str(self.response['code'])!='1' else (True,self.response['redirect'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        encrypted = "merch_id={}&merch_order_id={}&key={}".format(
            self.data.get("merch_id"),
            self.data.get("merch_order_id"),
            self.secret).encode("utf-8")

        sign = hashlib.md5(encrypted).hexdigest().upper()

        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

        if not self.data.get("merch_id") or self.data.get("merch_id")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")

        if str(self.data.get("code")) == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("merch_order_id"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")
            PayCallLastPass().run(order=order)

class LastPass_CHUANGYUAN_YUANSHENG(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.zfbtd66.xyz/api/createOrder"
        self.secret = "040244ffd1dd4c5582587a26d404510b"
        self.businessId = "19081217015810004"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        print(encrypted)
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):

        result = request(method='POST', url=self.create_order_url, data=self.data,json=self.data)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('appId',self.businessId)
        self.data.setdefault('productName','会员充值')
        self.data.setdefault('returnUrl',url_join("/pay/#/juli"))

        self._sign()

        print(self.data)

        try:
            self._request()
            print(self.response)
            return (False, self.response['msg']) if str(self.response['code'])!='0' else (True,self.response['obj'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        self.check_sign()

        if not self.data.get("appId") or self.data.get("appId")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")

        try:
            order = Order.objects.select_for_update().get(ordercode=self.data.get("orderNo"))
        except Order.DoesNotExist:
            raise PubErrorCustom("订单号不正确!")

        if order.status == '0':
            raise PubErrorCustom("订单已处理!")
        PayCallLastPass().run(order=order)

class LastPass_GUAISHOU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://pay.cc8859.com/apisubmit"
        self.secret = "5f79056afd95cd91526659888bf81e042697289e"
        self.businessId = "201903"

        self.response = None

    def _request(self):

        result = request(method='POST', url=self.create_order_url, data=self.data)

        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):

        self.data.setdefault("version","1.0")
        self.data.setdefault('customerid',self.businessId)
        self.data.setdefault('userid','userid')
        self.data.setdefault('paytype','alipay')
        self.data.setdefault('returnurl',url_join("/pay/#/juli"))

        self.data['total_fee'] = "%.2f"%(self.data['total_fee'])

        encrypted = "version={}&customerid={}&userid={}&total_fee={}&sdorderno={}&notifyurl={}&returnurl={}&{}".format(
            self.data.get('version'),
            self.data.get('customerid'),
            self.data.get('userid'),
            self.data.get('total_fee'),
            self.data.get('sdorderno'),
            self.data.get('notifyurl'),
            self.data.get('returnurl'),
            self.secret).encode("utf-8")

        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()
        self.data['create_order_url'] = self.create_order_url

        return self.data


    def call_run(self):

        print(self.data)
        encrypted = "customerid={}&status={}&sdpayno={}&sdorderno={}&total_fee={}&paytype={}&{}".format(
            self.data.get('customerid'),
            self.data.get('status'),
            self.data.get('sdpayno'),
            self.data.get('sdorderno'),
            self.data.get('total_fee'),
            self.data.get('paytype'),
            self.secret).encode("utf-8")
        sign = hashlib.md5(encrypted).hexdigest()
        if sign != self.data['sign']:
            raise PubErrorCustom("验签失败!")

        if str(self.data.get("status")) == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("sdorderno"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_TIGER(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://xd.kzf360.com/Pay_Index.html"
        self.secret = "8eoi5ugosstw7e5rj5ewzm7wz5mgusch"
        self.businessId = "10010"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)

        self.response = result.text
        logger.info(self.response)

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        # self.data.setdefault('pay_bankcode',"904")
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        self.data.setdefault('create_order_url',self.create_order_url)

        return self.data

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_XINGHE(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://api.osaky.cn/customer.pay"
        self.secret = "F0VKITMAYWBPYDIO3E7YZEBRGDSEYXFL"
        self.businessId = "xin400915198633"

        self.response = None


    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted+self.secret).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        signtype = self.data.pop('sign_type',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        print(json.dumps(self.data))
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response=json.loads(result.content.decode('utf-8'))
        print(self.response)


    def run(self):
        self.data.setdefault('mer_id',self.businessId)
        self.data.setdefault('timestamp',self.obtaindate())
        self.data.setdefault('terminal',"ALI_PAY_WAP")
        self.data.setdefault('version',"01")
        self.data.setdefault('backurl',url_join("/pay/#/juli"))
        self.data.setdefault('failUrl', url_join("/pay/#/juli"))
        self.data.setdefault('goodsName',"会员充值")
        self._sign()

        self.data.setdefault('sign_type',"md5")

        try:
            self._request()
            return (False, self.response['msg']) if str(self.response['result'])!='success' else (True,self.response['data']['trade_qrcode'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()

        if self.data.get("result") == 'success' and self.data.get('status')=='成功':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("businessnumber"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_CZKJ(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #生产环境
        self.create_order_url="http://ljjhf.elalpy.com/api/recharge/index"

        self.secret = "903b0677-4143-4de3-ade0-68e8b7dd2d68"
        self.businessId = "1037"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True,timeout=2)

        print(result.content)

        self.response = result.content.decode('utf-8')

    def run(self):
        self.data.setdefault('version','2')
        self.data.setdefault('merchant_number',self.businessId)
        self.data.setdefault('brower_url',url_join("/pay/#/juli"))
        self.data.setdefault('order_time',UtilTime().timestamp)
        self.data.setdefault('pay_type',2)
        self._sign()

        self._request()

        return self.response

    def call_run(self):
        self.check_sign()

        if self.data.get("status") == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("order_id"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_YUANLAI(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://mobile.shanjus.com/offline/outsideOrderPay"
        self.secret = "68838061a52e9b8c347dc6adc54da4e4"
        self.businessId = "1740"

        self.response = None

    def run(self):
        self.data.setdefault('shopId',self.businessId)

        print(self.data)

        encrypted = "{}{}{}{}".format(
            self.data.get('orderId'),
            self.data.get('price'),
            self.data.get('shopId'),
            self.secret).encode("utf-8")

        self.data['sign'] = hashlib.md5(encrypted).hexdigest()
        self.data['create_order_url'] = self.create_order_url

        print(self.data)

        return self.data

    def call_run(self):

        encrypted = "{}{}{}{}{}".format(
            self.data.get('orderId'),
            self.data.get('payTime'),
            self.data.get('price'),
            self.data.get('subNumber'),
            self.secret).encode("utf-8")


        print(encrypted)

        sign = hashlib.md5(encrypted).hexdigest()

        if sign != self.data.get('sign'):
            raise PubErrorCustom("签名不正确!")


        try:
            order = Order.objects.select_for_update().get(ordercode=self.data.get("orderId"))
        except Order.DoesNotExist:
            raise PubErrorCustom("订单号不正确!")

        if order.status == '0':
            raise PubErrorCustom("订单已处理!")

        PayCallLastPass().run(order=order)

class LastPass_JINGSHA(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://h.cc8859.com/apisubmit"
        self.secret = "5e13e427f5e15ccf129f05fd106955e5462e26db"
        self.businessId = "300005"

        self.response = None

    def _request(self):

        result = request(method='POST', url=self.create_order_url, data=self.data)

        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):

        self.data.setdefault("version","1.0")
        self.data.setdefault('customerid',self.businessId)
        self.data.setdefault('userid','userid')
        self.data.setdefault('paytype','alipay')
        self.data.setdefault('returnurl',url_join("/pay/#/juli"))

        self.data['total_fee'] = "%.2f"%(self.data['total_fee'])

        encrypted = "version={}&customerid={}&userid={}&total_fee={}&sdorderno={}&notifyurl={}&returnurl={}&{}".format(
            self.data.get('version'),
            self.data.get('customerid'),
            self.data.get('userid'),
            self.data.get('total_fee'),
            self.data.get('sdorderno'),
            self.data.get('notifyurl'),
            self.data.get('returnurl'),
            self.secret).encode("utf-8")

        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()
        self.data['create_order_url'] = self.create_order_url

        return self.data


    def call_run(self):

        print(self.data)
        encrypted = "customerid={}&status={}&sdpayno={}&sdorderno={}&total_fee={}&paytype={}&{}".format(
            self.data.get('customerid'),
            self.data.get('status'),
            self.data.get('sdpayno'),
            self.data.get('sdorderno'),
            self.data.get('total_fee'),
            self.data.get('paytype'),
            self.secret).encode("utf-8")
        sign = hashlib.md5(encrypted).hexdigest()
        if sign != self.data['sign']:
            raise PubErrorCustom("验签失败!")

        if str(self.data.get("status")) == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("sdorderno"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_ANJIE(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://anjieapi.teebsdauhuhuu.work/v2/precreate_v2.ashx"

        # self.create_order_url="http://requestbin.net/r/1crsgiq1"
        self.secret = "zKU7ppP5uqYC7HF3c2vP9yRJ6TfL8Ilg"
        self.businessId = "8085004732525943"

        self.response = None

    def _request(self):

        result = request(method='POST', url=self.create_order_url, data=self.data)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('appid',self.businessId)

        encrypted = "{}{}{}".format(
            self.data.get("appid"),
            self.secret,
            self.data.get('out_order_no')).encode("utf-8")

        print(encrypted)

        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        try:
            print(self.data)
            self._request()
            print(self.response)
            return (False, self.response['Msg']) if str(self.response['code'])!='0' else (True,self.response['url'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        encrypted = "{}{}{}".format(
            self.data.get("appid"),
            self.secret,
            self.data.get('out_order_no')).encode("utf-8")

        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        sign = hashlib.md5(encrypted).hexdigest()

        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

        try:
            order = Order.objects.select_for_update().get(ordercode=self.data.get("out_order_no"))
        except Order.DoesNotExist:
            raise PubErrorCustom("订单号不正确!")

        if order.status == '0':
            raise PubErrorCustom("订单已处理!")

        if float(order.amount) != float(self.data.get("returnamount")):
            raise PubErrorCustom("金额不符,不予回调!")
        PayCallLastPass().run(order=order)

class LastPass_hahapay(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.hahapay.xyz/Pay_Index.html"
        self.secret = "cpcl7hdzfngvpnrq4iz9sw3xg7s0vto7"
        self.businessId = "10122"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_SHUIJING(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://api.golosa.cn/customer.pay"
        self.secret = "4LXKHOCQJSJ5IJSAVSQYCYB5VOF66NUZ"
        self.businessId = "xin070919194666"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted+self.secret).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        signtype = self.data.pop('sign_type',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        print(json.dumps(self.data))
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response=json.loads(result.content.decode('utf-8'))
        print(self.response)


    def run(self):
        self.data.setdefault('mer_id',self.businessId)
        self.data.setdefault('timestamp',self.obtaindate())
        self.data.setdefault('terminal',"ALI_PAY_WAP")
        self.data.setdefault('version',"01")
        self.data.setdefault('backurl',url_join("/pay/#/juli"))
        self.data.setdefault('failUrl', url_join("/pay/#/juli"))
        self.data.setdefault('goodsName',"会员充值")
        self._sign()

        self.data.setdefault('sign_type',"md5")

        try:
            self._request()
            return (False, self.response['msg']) if str(self.response['result'])!='success' else (True,self.response['data']['trade_qrcode'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()

        if self.data.get("result") == 'success' and self.data.get('status')=='成功':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("businessnumber"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_ALLWIN(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #生产环境
        self.create_order_url="http://47.56.193.188/api_new/business/create_order"
        self.secret = "ENAMHOGK7KOX5MGY"
        self.businessId = "6"

        self.response = None

    def _request(self):
        print(json.dumps(self.data))
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response=json.loads(result.content.decode('utf-8'))
        print(self.response)

    def run(self):
        self.data.setdefault('businessid',self.businessId)
        self.data.setdefault('paytypeid','1')
        self.data.setdefault('ismobile',"0")

        encrypted = ("{}{}{}{}{}{}{}".format(
            self.secret,
            self.data['businessid'],
            self.data['paytypeid'],
            self.data['down_ordercode'],
            self.data['client_ip'],
            self.data['amount'],
            self.secret)).encode("utf-8")

        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        try:
            self._request()
            return (False, self.response['msg']) if str(self.response['rescode'])!='10000' else (True,self.response['data']['path'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        encrypted = ("{}{}{}{}{}{}{}".format(
            self.secret,
            self.data['businessid'],
            self.data['ordercode'],
            self.data['down_ordercode'],
            self.data['amount'],
            self.data['pay_time'],
            self.secret)).encode("utf-8")

        sign = hashlib.md5(encrypted).hexdigest()

        print(encrypted)
        print(sign)
        print(self.data)

        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")


        if self.data.get('status')=='00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("down_ordercode"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_SHUIJING_NEW(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://pay.51vza.cn/v2/toPay.do"
        self.secret = "fca31fd15973a526333817e8e9a6f83b"
        self.businessId = "1710"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key'] = self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted[:-1]).encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        signtype = self.data.pop('sign_type',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        print(result.content)
        self.response=json.loads(result.content.decode('utf-8'))

    def run(self):

        self.data.setdefault('payType',"34")
        self.data.setdefault('merchantId',self.businessId)
        self.data.setdefault('productName',"淘宝代付")
        self.data.setdefault('remark',"remark")

        self._sign()

        self.data.setdefault('create_order_url', self.create_order_url)

        print(self.data)

        return self.data

        #
        # try:
        #     self._request()
        #     return (False, self.response['msg']) if str(self.response['code'])!='200' else (True,self.response['obj']['url'])
        # except Exception as e:
        #     return (False,str(e))

    def call_run(self):
        self.check_sign()

        if  str(self.data.get('code')) =='200':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("tradeNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_YANXINGZHIFU(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.6yz86.cn/Pay_Index.html"

        self.secret = "gli14pwx4z81go3ruzexhhipfpb03ex7"
        self.businessId = "10303"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key'] = self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign', False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)

        self.response = result.text
        logger.info(self.response)

    def run(self):
        self.data.setdefault('pay_memberid', self.businessId)
        self.data.setdefault('pay_applydate', self.obtaindate())
        # self.data.setdefault('pay_bankcode',"904")
        self.data.setdefault('pay_callbackurl', url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname', "商品")

        self.data.setdefault('create_order_url', self.create_order_url)

        return self.data

    def call_run(self):
        self.check_sign()
        if not self.data.get("memberid") or self.data.get("memberid") != self.businessId:
            raise PubErrorCustom("商户ID不存在!")
        if not self.data.get("amount"):
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("orderid"):
            raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_BAWANGKUAIJIE(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)

        #订单生成地址
        self.create_order_url="http://orderpay.xincheng-sh.com:8088/webwt/unionH5Pay/orderreturnPay.do"


        #代付地址
        self.daifu_url = "http://orderpay.xincheng-sh.com:8088/webwt/pay/gateway.do"

        self.secret = "fcdd45eba6164b9cb2affed11b205d50"

        #私钥
        self.si_secret = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCN1aC9bqGq8jv/zLmuU06UMxE1oSaI3OcgKFDNgpNpGtMgmA/xz0Loshd/EMx9LKCtmxnRJPwHfa4weV8ttYzxyvZn2ZMPm92mZY/SPQrbcZ9xqlPDqT4G1fzXQg+45JCBS0+e6aSdW2ohcLw9EAzHf5LMI8d78t4rW7rvZTplQ8Jz37Tuixt0K58/k426cnjtrHWmYBBWbagWrFPbkvFL73+Pqb7ssRocMiWvZIRneEH9kHpRPwmou7nyN9LvhJ5jnRH9lk+4o3YFVOh8thU3RvKWw5K4EdHZUguMj8I6i2n1IbKlQcVMuyqjh44y9tj0ZwJUK4bqdoUO8JVEpW+NAgMBAAECggEAB6wLktOeKRoLRs3zKUvWT0vn3WfHJtYUJngnzsYGZUQPMY8oJaNZci7X+IaXGRpF4r4mClseyuTwfCzEijts0VNyOrHZM5nxxmNuAShOIwqlXkehWk8YTNRcZeRr50ttyaCiQO1QezaLqh1oAUGR/2SWMzaoPrsna1794J8wJnQMPbeI3XkM7tZx7nHetHiAuWqt38qaSRhpd+TYewkz5e1XpGLSoypqM/jDrCdnQ2uYgQhR3/60RT+2hf2t8ffZth4QbkNoxnA1n2cKFzAF9SOhXAP72g9cWpk5mweoh02jrKct0+qN7/RTRtkbvvvqlYgiSXoSHA+ftiYfKV/NAQKBgQDBZ4bgg52QgN6E/k7r8n4KbLjdd6xdgPSranyjOY9Q0DMg7OEjX5/uy9u2GYuImfeU3mcBSyfAffwVcxmk9xpxfMTug4ls8ZuXmutqhci11dLjnMiSe41Yp8UdzKtvc+KZxOEhO2hRWgHTJdfqKMkAZfVX4BKVpoRQg1jy5q3lwQKBgQC7vUnW31f1HRYFCCkt/y8OP2yIVV/aI+tVeWWbaQ9Uk58U7LKUnooHii8IUx2zmeEo/woQ8Kx2KPHGmmZ4hWRZY1uscZzg6TBy6p300CPPzobe1ca6L25rCt++bkVEVf4sGKYRFOXP6Zsjs2LDA1fVazlHjENvMqJHxU28i4l0zQKBgQClxIJKdQTcElinTQGAInv9m2poCGboTdtoAQGLNY6tCYaJNf9SPmfqWTicQBDkqHMYWfeXmD8eMd2a1OiqCFHV68cvV/a2Ne/SZapZxwldMURsarlPNC7WShYdkItwH7edbK45uZ2T/L2LqOgDf6moebtr8lZ7hhnqmGno5+ctAQKBgHatyUDI/VxY37OcnhOSrlduZpikh6xpanok/MNKncNUcosSui1TL2RmySaVDECd9QUqfF2LFyq25Wgr8L0dbftH4QrY41gWcWcjw2igLxNNtlqlfzPxifam8Bv8r1LsnXmYt1ozALf3L/hYjQVEVsD2QEZnd7WSp52BL4wSFXm9AoGAPxmXGft3umFh3Gg1j0iMXqOm1VxPnlelx5KY+HbUISkld71NbiLGqnL3k/h5j2CiVnw7AOWOM1wupYlIIr3jbxToem2eEEJNtzxIBCDklNvnaoGHdg5u7ra5IWJy4yJEYwINZdyUFbY3cOZGDSZqEHp4ziDUkRxWX5vvBEnn8/s="
        self.si_secret = "-----BEGIN RSA PRIVATE KEY-----\n" + self.si_secret + "\n-----END RSA PRIVATE KEY-----"
        #公钥
        #self.public_secret = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA7wGnoHC8BrqoppkvjshSi2gtJhp3ogy7nLsnNhqiCi3P3ZVmHYehcqbPmJuyIWQ+ILAIDfCcObSYqYZW6ozEJ3UrrghyszaWpD4YM8j3+5i+HMNqHt9tDzKigsaCPw1KKZKrNvXkMZ0ydmsEZ1zdJvE7whA3cAsjA62CNl3Aii25d1SjJisOVg20XcKHPLZKSUVScFdJ/tG19bpe8V3poq85087sVz3rniisjdKTbXTbxM2Nkpkt1IjmRfXrHpW/805L/uPpCVqo125on4yY2nIFY42e0GmS/LG6YM55QZ+9CvC1P8PEoNv0cArbdqpmBBfGGxyT2LfkZM7DvrTQIwIDAQAB"
        self.public_secret = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA7wGnoHC8BrqoppkvjshSi2gtJhp3ogy7nLsnNhqiCi3P3ZVmHYehcqbPmJuyIWQ+ILAIDfCcObSYqYZW6ozEJ3UrrghyszaWpD4YM8j3+5i+HMNqHt9tDzKigsaCPw1KKZKrNvXkMZ0ydmsEZ1zdJvE7whA3cAsjA62CNl3Aii25d1SjJisOVg20XcKHPLZKSUVScFdJ/tG19bpe8V3poq85087sVz3rniisjdKTbXTbxM2Nkpkt1IjmRfXrHpW/805L/uPpCVqo125on4yY2nIFY42e0GmS/LG6YM55QZ+9CvC1P8PEoNv0cArbdqpmBBfGGxyT2LfkZM7DvrTQIwIDAQAB"
        self.public_secret = "-----BEGIN PUBLIC KEY-----\n" + self.public_secret + "\n-----END PUBLIC KEY-----"

        self.data.setdefault('agtId', "19101009")
        self.data.setdefault('merId', "1910100909")

    def rsa_sign(self,message):

        encrypted = message.encode("utf-8")
        private_key = RSA.importKey(self.si_secret)

        h = SHA256.new(encrypted)

        signature = PKCS1_v1_5.new(private_key).sign(h)
        return base64.b64encode(signature)

    def rsa_design(self,signature,msg):

        msg = msg.encode("utf-8")
        public_key = RSA.importKey(self.public_secret)

        hash_obj = SHA256.new(msg)

        try:
            PKCS1_v1_5.new(public_key).verify(hash_obj, base64.b64decode(signature))
            return True
        except (ValueError, TypeError):
            return False

    def _sign(self,data=None):

        valid_data = {}
        # 去掉value为空的值
        for item in data:
            valid_data[item] = data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key'] = self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = (encrypted[:-1]).encode("utf-8")

        return hashlib.md5(encrypted).hexdigest().upper()

    def rsa2_sign(self,sign):
        return self.rsa_sign(sign)

    def check_sign(self,sign,md5sign):
        if not self.rsa_design(sign,md5sign):
            return False
        else:
            return True


    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data,verify=True)
        return result.content.decode('utf-8')

    def _request_daifu(self,url,data):

        result = request(method='POST', url=url, json=data,verify=True,headers={
            "Content-Type":'application/json'
        })
        return json.loads(result.content.decode('utf-8'))

    def df_bal_query(self):
        self.data.setdefault("tranCode","2103")
        self.data.setdefault("nonceStr",str(UtilTime().timestamp))
        sign = self._sign(self.data)

        data = {
            "REQ_HEAD" : {
                "sign" : self.rsa2_sign(sign).decode('utf-8')
            },
            "REQ_BODY" : self.data.copy()
        }

        res = self._request_daifu(self.daifu_url,data)

        sign = res['REP_HEAD']['sign']

        if not self.check_sign(sign,self._sign(res['REP_BODY'])):
            PubErrorCustom("验签失败!")


    def run(self):
        # self.data.setdefault('agtId',self.agtId)
        # self.data.setdefault('merId',self.businessId)
        # self.data.setdefault("memberId","1")

        self.data.setdefault("orderTime",str(UtilTime().arrow_to_string(format_v="YYYYMMDD")))

        self.data.setdefault("pageReturnUrl",url_join("/pay/#/juli"))

        self.data.setdefault('goodsName',"goodsName")
        self.data.setdefault('bankCardNo', '1')
        self.data.setdefault('sign',self.rsa2_sign(self._sign(self.data)))

        return self._request()

    def call_run(self):

        sign = self.data.pop('sign')
        print(sign)
        print(self.data)
        if not self.check_sign(sign,self._sign(self.data)):
            raise PubErrorCustom("验签失败!")

        print(self.data.get('orderState'))
        if self.data.get('orderState') and str(self.data.get('orderState')) == '01':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderId"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)
        else:
            raise  PubErrorCustom("支付状态有误!")




    def df_return_content(self):


        cardno = "6226000000000000"
        name = "小明"
        bankname = "中国工商银行"
        type = "私"
        amount = 0.08
        bizhong = 'CNY'
        ordercode = "10000001"
        remark = "备注"

        content = "{},{},{},{},{},{},{},{},{}".format(
            cardno,
            name,
            bankname,
            type,
            amount,
            bizhong,
            '',
            ordercode,
            remark
        )
        print(content)
        return content


    def df_api(self):
        self.data.setdefault('customerNo', self.businessId)
        self.data.setdefault('inputCharset', "utf8")
        self.data.setdefault('payDate', UtilTime().arrow_to_string(format_v="YYYYMMDD"))
        self.data.setdefault('inputCharset', "00")

        self.data.setdefault('content',self.df_return_content())

        self._sign()

        self.data.setdefault('signType', "MD5")

class LastPass_JINGDONG(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://api.jd.com/routerjson"

        self.AccessToken = "392f4d0bd9ac4b188d8cf84819962930mgjk"
        self.AppKey = "0814C02450D81B1602035DD5D242D927"
        self.AppSecret = "0b05ddd2120d4562b5807648d80b334e"

        self.response = None

        self.goods = {}

        self.busis = {}

        self.data.setdefault('access_token',self.AccessToken)
        self.data.setdefault('app_key',self.AppKey)
        self.data.setdefault('timestamp',UtilTime().arrow_to_string())
        self.data.setdefault("v",'2.0')


    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}{}".format(item, valid_orders_data[item])
        encrypted = "{}{}{}".format(self.secret,encrypted,self.secret).encode("utf-8")
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def _request(self):

        print(self.data)
        result = request(method='POST', url=self.create_order_url, params=self.data,verify=True)

        self.response = json.loads(result.content.decode('utf-8'))
        print(self.response)

        try:
            return self.response['jingdong_generateRemoteOrderLink_responce']['generateRemoteOrderLink_result']['value']
        except Exception:
            PubErrorCustom("下单错误,请重新下单!")

    def _request_order_query(self):

        result = request(method='POST', url=self.create_order_url, params=self.data, verify=True)

        print(result.content)

        self.response = json.loads(result.content.decode('utf-8'))

        print(self.response)
        try:
            return True if self.response['jingdong_queryOrderInfoByPayLink_responce']['generateRemoteOrderLink_result']['value']['status'] == 2 else False
        except Exception:
            return False


    def get_good(self):

        bigamount = 100.0

        prices = []

        price = float(self.data.get('price'))
        while True:
            if price > bigamount:
                dprice = price / bigamount
                prices.append(bigamount)
                prices = prices * int(dprice)
                price = price % bigamount
            elif price > 0.0:
                prices.append(price)
                break
            else:
                break

        goods = [
            {
                "goodsId" : "48793865652",
                "price" : "$price==10.0",
                "goodsName" : '打气'
            },
            {
                "goodsId": "27856567458",
                "price": "$price==40.0",
                "goodsName": '洗车'
            },
            {
                "goodsId": "11178829081",
                "price": "$price==100.0",
                "goodsName": '打蜡'
            },
            {
                "goodsId": "47499979228",
                "price": "40.0<$price<50.0",
                "goodsName": '贴片补胎'
            },
            {
                "goodsId": "47499979229",
                "price": "50.0<=$price<90.0",
                "goodsName": '蘑菇钉补胎'
            },
        ]

        goodsList = []
        for item_price in prices:
            for item in goods:
                if eval(item['price'].replace('$price',"item_price")):
                    goodsList.append(item.get('goodsId'))

        if not len(goodsList) or len(goodsList) != len(prices):
            return None

        goodsStr = ""
        countStr = ""
        priceStr = ""
        for item in goodsList:
            goodsStr += "{},".format(item)
            countStr += "1,"
        for item in prices:
            priceStr += "{},".format(item)

        goodsStr=goodsStr[:-1]
        countStr=countStr[:-1]
        priceStr=priceStr[:-1]
        return [ goodsStr,countStr,priceStr ]

    def get_busi(self):

        jdObj = JdBusiList.objects.raw("""
            SELECT * FROM jdbusilist
            WHERE status='0' and maxnum>num-1 and maxamount > amount-%s ORDER BY RAND() LIMIT 1
        """,[str(self.data.get('price'))])

        jdObj = list(jdObj)
        if len(jdObj)>0:
            return jdObj[0].busi_id
        else:
            return None

    def run(self):

        goodsObj = self.get_good()
        if not goodsObj:
            raise PubErrorCustom("金额范围有误!")
        storeId = self.get_busi()
        if not storeId:
            raise PubErrorCustom("暂无店铺!")


        self.data.setdefault('method','jingdong.generateRemoteOrderLink')

        self.data.setdefault('360buy_param_json',json.dumps({
            "storeId":storeId,
            "deliveryWay":'10',
            "salesPin" : "aipeikeb5yc",
            "skuId" : goodsObj[0],
            "count" : goodsObj[1],
            "price" : goodsObj[2]
        }))

        self._sign()
        url = self._request()

        return {
            "url" : url,
            "storeId": storeId,
            "ordercode" :url.split('order/')[1],
            "goodsObj" : goodsObj
        }

    def queryOrder(self):

        print("开始查询京东订单回调处理!")
        orders = Order.objects.filter(isjd='0',status='1')
        self.data.setdefault('method', 'jingdong.queryOrderInfoByPayLink')

        for item in orders :
            print(item.jd_ordercode)
            self.data['360buy_param_json'] = ""

            self.data['360buy_param_json'] = json.dumps({
                "payLink" : item.jd_ordercode
            })

            self._sign()

            print(self.data)
            if self._request_order_query():

                jdObj = demjson.decode(item.jd_data)

                request_data = {
                    "orderid" : item.ordercode
                }

                print("request_data:",request_data)

                result = request('POST', url=urllib.parse.unquote('http://allwin6666.com/api/lastpass/jingdong_callback'), data=request_data,
                                 json=request_data, verify=False)

                if result.text != 'success':
                    print("请求对方服务器错误{}:{}".format(str(result.text),item.ordercode))

                try:
                    jdbusilist = JdBusiList.objects.get(busi_id=jdObj.get('storeId'))

                    jdbusilist.amount = float(jdbusilist.amount) + float(item.amount)
                    jdbusilist.num += 1
                    jdbusilist.save()
                except JdBusiList.DoesNotExist:
                    print("没有此店铺:{}".format(jdObj.get('storeId')))


    def call_run(self):

        try:
            order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
        except Order.DoesNotExist:
            raise PubErrorCustom("订单号不正确!")

        if order.status == '0':
            raise PubErrorCustom("订单已处理!")

        PayCallLastPass().run(order=order)



class ShouGongHandler(LastPassBase):

    def __init__(self,**kwargs):
        super().__init__(**kwargs)

    def call_run(self):

        try:
            order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
        except Order.DoesNotExist:
            raise PubErrorCustom("订单号不正确!")

        if order.status == '0':
            raise PubErrorCustom("订单已处理!")

        PayCallLastPass().run(order=order)

    def message_run(self):
        pass


class LastPass_JIAHUI(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://do.zengfou.cn/api/pay/create_order"
        self.secret = "J2G7GTMCNZZQNPG4FLS46U2WYOGQFHS7IAVJ6442CMPHEM2QEALBK0AUNV33M5IWRJ9ZFTJJULJ9CTELHAGRSZPCQR9LJYU1GMXFYX6JM6LTKZCPDKX7IMYTSE2BWVUW"
        self.businessId = 20000072

        self.appId = '9b1b7f74c5f8435d9cabf669b60cdfbc'

        # self.productId = '98c51ce4ac6f44d5aed38892d5bd09d1'

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('mchId',self.businessId)
        self.data.setdefault('appId',self.appId)

        self.data.setdefault('return_url', url_join("/pay/#/juli"))
        # self.data.setdefault('productId', self.productId)
        self.data.setdefault('currency','cny')

        # self.data.setdefault('productId', self.productId)
        self.data.setdefault('subject','商品P')
        self.data.setdefault('body', '商品P6666')

        # self.data.setdefault('pay_bankcode',"904")
        self._sign()


        try:
            self._request()
            print(self.response)
            return (False, self.response['retMsg']) if self.response['retCode']!='SUCCESS' else (True,self.response['payParams']['payUrl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        # self.check_sign()
        if not self.data.get("amount") :
            raise PubErrorCustom("金额不能为空!")
        if not self.data.get("mchOrderNo"):
            raise PubErrorCustom("商户订单号为空!")

        self.data["amount"] = float(self.data.get("amount")) / 100.0

        if str(self.data.get("status")) == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("mchOrderNo"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_ZHONGXING(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.bbw.ph/bbPay/orderInfoMd5"
        self.secret = "52cf773763285e84d0ab70b241fd75fe"
        self.AES_secret = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1UxzIjNGV6BC4bhyMAQ7yDkqEMVwuGGq 0X3CWr0+oErC/X6TIK85jkQsGMRdFF8jtZ/c+58Qj3TM70OpWsPx8XrbNWDK65U0xDenPQpOXKkP gJHGKJiJsiELc0tdw9uzrO8olza15BqP7CnDrNh3L/3i0/xhQ3VThN+pHzEwwwueh8Z/O4Rb4Wvt 9gjIX0vjl1K/VBeXmTBs1oVvMuJNJqsB2j6gPwASnl6a17voRdq52KGzbdgtwuPauZr6bM3+tDsz fgiyMChO/iwgJPfl9I4X2idg2FLA5+tezT5Sp2g4cOsG9ZavahpgsYQSVEqxE0hv6VV4ika2S2tf 6G+XLQIDAQAB"

        self.businessId = "LAW005"

        self.response = None

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('userName',self.businessId)
        self.data.setdefault('channelType',"1")
        self.data.setdefault('redirectUrl', url_join("/pay/#/juli"))
        self.data.setdefault('currency','cny')

        self.data.setdefault('businessid',self.businessId)
        self.data.setdefault('paytypeid','1')
        self.data.setdefault('ismobile',"0")

        encrypted = ("{}{}{}{}{}{}".format(
            self.data['userName'],
            self.data['orderNumber'],
            self.data['amount'],
            self.data['channelType'],
            self.data['notifyUrl'],
            self.secret)).encode("utf-8")

        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        print(self.data)

        try:
            self._request()
            print(self.response)
            return (False, self.response['msg']) if str(self.response['status'])!='1000' else (True,self.response['payUrl'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        print(self.data)
        encrypted = ("{}{}{}{}{}{}".format(
            self.data['userName'],
            self.data['orderNumber'],
            self.data['amount'],
            self.data['channelType'],
            self.data['tradeOrderNo'],
            self.secret)).encode("utf-8")

        sign = hashlib.md5(encrypted).hexdigest()

        if sign != self.data['sign']:
            raise PubErrorCustom("验签失败!")


        if str(self.data.get("status")) == 'PAYED':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderNumber"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_ZHAOXING(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://zx.zxlingshou.club/Index/api/pay"
        self.secret = "UjS5MdlJNJIw6U2YrU6qqpMZKCj2YywY"

        self.businessId = "10113"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('userid',self.businessId)
        self.data.setdefault('type',"102")

        self._sign()

        try:
            self._request()
            print(self.response)
            return (False, self.response['msg']) if str(self.response['code'])!='success' else (True,self.response['data'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):


        self.check_sign()

        if str(self.data.get("status")) == '2':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("innerorderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_TIANCHENG(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="https://www.ccnkyy.com/api/v3/cashier.php"
        self.secret = "c650442bfd6a36749a0c57c4802c5cbd"

        self.businessId = "TC19102517295"

        self.response = None

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('merchant',self.businessId)
        self.data.setdefault('qrtype',"aph5")
        self.data.setdefault('sendtime', UtilTime().timestamp)
        self.data.setdefault("risklevel",1)
        self.data.setdefault("backurl",url_join("/pay/#/juli"))


        encrypted = ("merchant={}&qrtype={}&customno={}&money={}&sendtime={}&notifyurl={}&backurl={}&risklevel={}{}".format(
            self.data['merchant'],
            self.data['qrtype'],
            self.data['customno'],
            self.data['money'],
            self.data['sendtime'],
            self.data['notifyurl'],
            self.data['backurl'],
            self.data['risklevel'],
            self.secret)).encode("utf-8")

        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        self.data.setdefault("create_order_url",self.create_order_url)
        return self.data

    def call_run(self):

        print(self.data)
        encrypted = ("merchant={}&qrtype={}&customno={}&sendtime={}&orderno={}&money={}&paytime={}&state={}{}".format(
            self.data['merchant'],
            self.data['qrtype'],
            self.data['customno'],
            self.data['sendtime'],
            self.data['orderno'],
            self.data['money'],
            self.data['paytime'],
            self.data['state'],
            self.secret)).encode("utf-8")

        sign = hashlib.md5(encrypted).hexdigest()

        if sign != self.data['sign']:
            raise PubErrorCustom("验签失败!")


        if str(self.data.get("state")) == '1':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("customno"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_IPAYZHIFUBAO(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="	http://20pay.vip/api/Gateway/create"
        self.secret = "742452DD4AB6D73449445FBF3F1D28E9"

        self.businessId = "200010033"

        self.response = None

    def _request(self):
        print(self.data)
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        print(result.text)
        print(result.content.decode('utf-8'))
        self.response =  json.loads(result.content.decode('utf-8'))

    def run(self):
        self.data.setdefault('account_id',self.businessId)
        self.data.setdefault('thoroughfare',"alipay_auto")
        self.data.setdefault('content_type', "json")
        self.data.setdefault("robin",1)
        self.data.setdefault("success_url",url_join("/pay/#/juli"))
        self.data.setdefault("error_url",url_join("/pay/#/juli"))


        encrypted = (str(self.data.get("amount")) +  str(self.data.get("out_trade_no")) ).encode("utf-8")
        print(encrypted)
        md5 = hashlib.md5(encrypted).hexdigest()

        encrypted = (self.secret.lower() + md5).encode('utf-8')
        print(encrypted)
        self.data['sign'] = hashlib.md5(encrypted).hexdigest()

        try:
            self._request()
            return (False, self.response['msg']) if str(self.response['code'])!='200' else (True,self.response['data']['jump_url'])
        except Exception as e:
            return (False,str(e))

    def call_run(self):

        print(self.data)
        encrypted = (str(self.data.get("amount")) + str(self.data.get("out_trade_no"))).encode("utf-8")
        print(encrypted)
        md5 = hashlib.md5(encrypted).hexdigest()

        encrypted = (self.secret.lower() + md5).encode('utf-8')
        print(encrypted)
        sign = hashlib.md5(encrypted).hexdigest()

        if sign != self.data['sign']:
            raise PubErrorCustom("验签失败!")

        if str(self.data.get("status")) == 'success':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("out_trade_no"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_YSLH(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://www.bianjiezf.com/Pay_Index.html"
        self.secret = "vodhb7l8qrg36whv1pz31p4jlrjv693w"
        self.businessId = "11041"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        self.check_sign()
        # if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
        #     raise PubErrorCustom("商户ID不存在!")
        # if not self.data.get("amount") :
        #     raise PubErrorCustom("金额不能为空!")
        # if not self.data.get("orderid"):
        #     raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)

class LastPass_JUXINGNEW(LastPassBase):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)


        #生产环境
        self.create_order_url="http://t01.jpttym.com/Pay_Index.html"
        self.secret = "wpw35kn5u2jdtu4fgo7pakuxyyiqoguo"
        self.businessId = "180778747"

        self.response = None

    def _sign(self):

        valid_data = {}
        # 去掉value为空的值
        for item in self.data:
            if str(self.data[item]) and len(str(self.data[item])):
                valid_data[item] = self.data[item]

        # 排序固定位置
        valid_data_keys = sorted(valid_data)
        valid_orders_data = OrderedDict()
        for key in valid_data_keys:
            valid_orders_data[key] = valid_data[key]

        valid_orders_data['key']=self.secret

        # 将数据变成待加密串
        encrypted = str()
        for item in valid_orders_data:
            encrypted += "{}={}&".format(item, valid_orders_data[item])
        encrypted = encrypted[:-1].encode("utf-8")
        self.data['pay_md5sign'] = hashlib.md5(encrypted).hexdigest().upper()

    def check_sign(self):
        sign = self.data.pop('sign',False)
        self._sign()
        if self.data['pay_md5sign'] != sign:
            raise PubErrorCustom("签名不正确")

    def Md5str(src):
        m = hashlib.md5(src.encode("utf8"))
        return m.hexdigest().upper()

    def obtaindate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _request(self):
        result = request(method='POST', url=self.create_order_url, data=self.data, verify=True)
        self.response = result.text

    def run(self):
        self.data.setdefault('pay_memberid',self.businessId)
        self.data.setdefault('pay_applydate',self.obtaindate())
        self.data.setdefault('pay_callbackurl',url_join("/pay/#/juli"))
        self._sign()

        self.data.setdefault('pay_productname',"商品")

        try:
            self._request()
            return (True,self.response)
        except Exception as e:
            return (False,str(e))

    def call_run(self):
        # self.check_sign()
        # if not self.data.get("memberid") or self.data.get("memberid")!= self.businessId:
        #     raise PubErrorCustom("商户ID不存在!")
        # if not self.data.get("amount") :
        #     raise PubErrorCustom("金额不能为空!")
        # if not self.data.get("orderid"):
        #     raise PubErrorCustom("商户订单号为空!")

        if self.data.get("returncode") == '00':
            try:
                order = Order.objects.select_for_update().get(ordercode=self.data.get("orderid"))
            except Order.DoesNotExist:
                raise PubErrorCustom("订单号不正确!")

            if order.status == '0':
                raise PubErrorCustom("订单已处理!")

            PayCallLastPass().run(order=order)


if __name__=="__main__":

    request_data = {
        "uid": "1",
        "amount": 1000.0,
        "outTradeNo": "5",
        "ip": "192.168.0.1",
        "notifyUrl": "http://allwin6666.com/api/pay_call/wechat_test"
    }
    res = LastPass_JLF(data=request_data).run()














