"""

发射点发射点发射点发射点发射点发射点发飞机拉萨大家发上来大家flash噶啥的vu阿斯顿哦按时间段垃圾上单龙卷风阿婆史丹佛安徽s

"""

#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

from celeryapp.lib.rules import Rules
import copy
import requests
import random
import base64
import json
from celeryapp.lib.common import HttpLog
from celeryapp.lib.scan_request import scan_request
import celeryapp.config 
from html_similarity import similarity, structural_similarity, style_similarity


class Rule(Rules):
    def scan(self,request):
        self.info = {}
        #type 长度不要过12
        self.type = "NOSQLI" 
        self.level = 'MEDIUM'
        #origin_request = copy.deepcopy(request)
        self.payloads = [              
            {   
                'value': '\'',
                'check': '',
                'type': 'append',
                'location':6
            },
            {   
                'value': '\'',
                'check': '',
                'type': 'replace',
            },         
            {   
                'value': '[$ne]',
                'check': '',
                'type': 'append',
                'payload_on_key':True,
                'url_encode':False,
            }
        ]
       
        #TODO poc_change添加poc位置信息
        self.poc_change()
        self.do_scan()

    def check_page(self):
        ...
        return True


    def check_res(self,p):
        self.bug = False

        #报错
        error_flags = ['MongoError','Uncaught MongoDB\\Driver\\Exception\\CommandException: unknown operator',  'unterminated string literal', 'Cast to string failed for value','SyntaxError']
        for e in error_flags:
            if e in self.res.text:
                self.bug = True
                break
            else:
                self.bug = False
                        
        #请求响应
        origin_body = str(base64.b64decode(self.origin_request.get('response').get('body')),'utf-8','ignore')
        
        """s1 = similarity(self.res.text,origin_body)
        s2 = structural_similarity(self.res.text,origin_body)
        s3 = style_similarity(self.res.text,origin_body)
        s4 = 0.3*s1 + 0.7*s2"""
        if self.res.status_code == 200 and self.check_page():
            #if (self.res.text == str(base64.b64decode(self.origin_request.get('response').get('body')),'utf-8','ignore')):
            if structural_similarity(self.res.text,origin_body) > 0.9:
                self.bug = False