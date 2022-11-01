#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

from asyncio.log import logger
from cgitb import text
from difflib import SequenceMatcher
from os import remove
from pickle import TRUE

from bs4 import BeautifulSoup
from celeryapp.lib.rules import Rules
import re
import uuid
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
                'value': '[$ne]',
                'check': '',
                'type': 'append',
                'payload_on_key':True,
                'url_encode':False,
            },
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
            }
        ]
        
        #TODO poc_change添加poc位置信息
        self.poc_change()
        self.do_scan()


    def check_res(self,p):
        self.bug = False
        print("slef.payloads_value值：" + self.payloads_value)
        if self.payloads_value == '[$ne]':
            request_after_do_scan = self.res.request 

            #保存构造好的请求响应，以供后续用来比较使用        
            res_after_do_scan = copy.deepcopy(self.res) 
            res_after_do_scan_text = res_after_do_scan.text 

            #原始请求响应
            origin_body = str(base64.b64decode(self.origin_request.get('response').get('body')),'utf-8','ignore')
        
            if self.checkStability():
                #使用构造好的请求响应，来覆盖self.res
                self.res = res_after_do_scan

                if self.res.status_code == 200:
                    if SequenceMatcher(None, self.res.text, origin_body).ratio() > 0.9:
                        self.bug = True
                
            else:
                #使用构造好的请求响应，来覆盖self.res
                self.res = res_after_do_scan
                #print(self.res.text)
                
                #去动态内容前的相似度
                ratio_before_remove = SequenceMatcher(None, self.res.text, origin_body).ratio()
                print("去除动态内容前的相似度：", ratio_before_remove)

                #重放原始请求，两次原始请求比较，得到dynamicMarkings，再删除动态内容
                self.check_compliance()
                self.origin_res = copy.deepcopy(self.res)
                origin_res_text_2 = self.origin_res.text
                checkDynamicContent(origin_body, origin_res_text_2)
                origin_body_2 = removeDynamicContent(origin_body)

                #重放构造请求，两次构造请求比较，得到dynamicMarkings，再删除动态内容
                self.res = res_after_do_scan
                payload_res_text_1 = res_after_do_scan 
                payload_res_text_1 = res_after_do_scan.text
                #重放构造请求
                self.send_scan_request(r=request_after_do_scan)
                payload_res = copy.deepcopy(self.res)
                payload_res_text_2 = payload_res.text
                checkDynamicContent(payload_res_text_1, payload_res_text_2)
                text_2 = removeDynamicContent(payload_res_text_1)


                #去动态内容后的相似度
                ratio_after_remove = SequenceMatcher(None, text_2, origin_body_2).ratio()
                print("去除动态内容后相似度：", ratio_after_remove)
                
                #去除HTML标签
                text_2_html = BeautifulSoup(text_2, 'html.parser')
                text_2_html_remove_tap = text_2_html.get_text()
                origin_body_2_html = BeautifulSoup(origin_body_2, 'html.parser')
                origin_body_2_html_remove_tap = origin_body_2_html.get_text()
                ratio_html_remove_tap = SequenceMatcher(None, text_2_html_remove_tap, origin_body_2_html_remove_tap).ratio()
                print("去除动态内容且去除HTML标签后的相似度：", ratio_html_remove_tap)
                #print(text_2_html_remove_tap)
                #print(origin_body_2_html_remove_tap)

                if self.res.status_code == 200:
                    #if SequenceMatcher(None,text_2,origin_body_2).ratio() > 0.8:
                    if ratio_html_remove_tap > 0.8:
                        self.bug = True
            
        else:
            #报错
            error_flags = ['MongoError','Uncaught MongoDB\\Driver\\Exception\\CommandException: unknown operator',  'unterminated string literal', 'Cast to string failed for value','SyntaxError']
            for e in error_flags:
                if e in self.res.text:
                    self.bug = True
                    break
                else:
                    self.bug = False

        
        
        
        
    
    #重放下的页面响应是否相同，相同，则无动态内容；不同，则处理动态内容
    def checkStability(self):
        """
        使用相同数据的原始请求，根据响应文本是否相等，从而判定是否稳定
        """

        self.check_compliance()
        self.res_0 = copy.deepcopy(self.res)
        firstPage = self.res_0.text
        self.check_compliance()
        self.check_compliance()
        self.check_compliance()
        self.check_compliance()
        self.res_1 = copy.deepcopy(self.res)
        secondPage = self.res_1.text

        pageStable = (firstPage==secondPage)

        if pageStable:
            infoMsg = "target URL content is stable."
        else:
            infoMsg = "target URL content is not stable."
            #不做处理，不使用通用的前后缀来处理，使用各自单独得到的前后缀来处理，减少错误处理
            #checkDynamicContent(firstPage, secondPage)
        return pageStable

def trimAlphaNum(value):
    """
    Trims alpha numeric characters from start and ending of a given value

    >>> trimAlphaNum('AND 1>(2+3)-- foobar')
    ' 1>(2+3)-- '
    """
    
    """while value and value[-1].isalnum():
        value = value[:-1]

    while value and value[0].isalnum():
        value = value[1:]"""

    return value



dynamicMarkings=[]
DYNAMICITY_BOUNDARY_LENGTH = 35

def findDynamicContent(firstPage, secondPage):
    #设置未空，重新赋值
    global dynamicMarkings
    dynamicMarkings = []
    if not firstPage or not secondPage:
        return
    
    blocks = list(SequenceMatcher(None, firstPage, secondPage).get_matching_blocks())
    
    for block in blocks[:]:
        (_,_,length) = block
        if length <= 2* DYNAMICITY_BOUNDARY_LENGTH:
            blocks.remove(block)

    # Making of dynamic markings based on prefix/suffix principle
    if len(blocks) > 0:
        blocks.insert(0, None)
        blocks.append(None)
        for i in range(len(blocks) - 1):
            prefix = firstPage[blocks[i][0]:blocks[i][0] + blocks[i][2]] if blocks[i] else None
            suffix = firstPage[blocks[i + 1][0]:blocks[i + 1][0] + blocks[i + 1][2]] if blocks[i + 1] else None

            if prefix is None and blocks[i + 1][0] == 0:
                continue

            if suffix is None and (blocks[i][0] + blocks[i][2] >= len(firstPage)):
                continue

            if prefix and suffix:
                #后Dynamicity_Boundary_Length个
                prefix = prefix[-DYNAMICITY_BOUNDARY_LENGTH:]
                #前Dynamicity_Boundary_Length个
                suffix = suffix[:DYNAMICITY_BOUNDARY_LENGTH]

                for _ in (firstPage, secondPage):
                    match = re.search(r"(?s)%s(.+)%s" % (re.escape(prefix), re.escape(suffix)), _)
                    if match:
                        infix = match.group(1)
                        if infix[0].isalnum():
                            prefix = trimAlphaNum(prefix)
                        if infix[-1].isalnum():
                            suffix = trimAlphaNum(suffix)
                        break

            dynamicMarkings.append((prefix if prefix else None, suffix if suffix else None))
            
    #print("findDynamicContent中的dynamicMarkings:",dynamicMarkings)        
    if len(dynamicMarkings) > 0:
        infoMsg = "dynamic content marked for removal (%d region%s)" % (len(dynamicMarkings), 's' if len(dynamicMarkings) > 1 else '')


def checkDynamicContent(firstPage, secondPage):

    MAX_DIFFLIB_SEQUENCE_LENGTH = 10 * 1024 * 1024
    UPPER_RATIO_BOUND = 0.98

    if any(page is None for page in (firstPage, secondPage)):
        warnMsg = "can't check dynamic content because of lack of page content."
        return

    if firstPage and secondPage and any(len(_) > MAX_DIFFLIB_SEQUENCE_LENGTH for _ in (firstPage, secondPage)):
        ratio = None
    else:
        s = SequenceMatcher(None,firstPage,secondPage)
        ratio = s.quick_ratio()
    #测试，动态内容少的情况
    #ratio = 0.99
    if ratio <= UPPER_RATIO_BOUND:
        findDynamicContent(firstPage, secondPage)

def removeDynamicContent(page):
    """
    Removing dynamic content from supplied page basing removal on
    precalculated dynamic markings
    """
    if dynamicMarkings == []:
        return page
    if page:
        for item in dynamicMarkings:
            prefix, suffix = item

            if prefix is None and suffix is None:
                continue
            elif prefix is None:
                #如果没有前缀，则删除suffix后缀前面的内容
                page = re.sub(r"(?s)^.+%s" % re.escape(suffix), suffix.replace('\\', r'\\'), page)
            elif suffix is None:
                #如果没有后缀，则删除prefix前缀后面的内容
                page = re.sub(r"(?s)%s.+$" % re.escape(prefix), prefix.replace('\\', r'\\'), page)
            else:
                #前后缀都存在，则删除前缀和后缀之间的内容
                page = re.sub(r"(?s)%s.+%s" % (re.escape(prefix), re.escape(suffix)), "%s%s" % (prefix.replace('\\', r'\\'), suffix.replace('\\', r'\\')), page)

    return page