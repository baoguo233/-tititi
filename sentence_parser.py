# -*- coding: utf-8 -*-
'''
Created on 2018年11月17日

@author: Zhukun Luo
Jiangxi university of finance and economics
'''
import os
from pyltp import Segmentor, Postagger, Parser, NamedEntityRecognizer, SementicRoleLabeller
from pyltp import SentenceSplitter
import json
import codecs
import pandas as pd
from pymongo import MongoClient
from _collections import defaultdict
from bson import json_util
from bson import ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)
class LtpParser:
    def __init__(self):
        LTP_DIR = 'E:\LTP\ltp_data_v3.4.0'  # ltp模型目录的路径
        self.segmentor = Segmentor()
        self.segmentor.load(os.path.join(LTP_DIR, "cws.model"))# 分词模型路径，模型名称为`cws.model`

        self.postagger = Postagger()
        self.postagger.load(os.path.join(LTP_DIR, "pos.model"))# 词性标注模型路径，模型名称为`pos.model`

        self.parser = Parser()
        self.parser.load(os.path.join(LTP_DIR, "parser.model"))# 依存句法分析模型路径，模型名称为`parser.model

        self.recognizer = NamedEntityRecognizer()
        self.recognizer.load(os.path.join(LTP_DIR, "ner.model"))# 命名实体识别模型路径，模型名称为`ner.model`

        self.labeller = SementicRoleLabeller()
        self.labeller.load(os.path.join(LTP_DIR, "pisrl_win.model"))# 语义角色标注模型目录路径，模型目录为`srl`。注意该模型路径是一个目录，而不是一个文件。

    '''语义角色标注'''
    def format_labelrole(self, words, postags):
        arcs = self.parser.parse(words, postags)
        roles = self.labeller.label(words, postags, arcs)
        for role in roles:
            print(words[role.index])
            print(role.index, "".join(["%s:(%d,%d)"%(arg.name,arg.range.start,arg.range.end) for arg in role.arguments]))
        roles_dict = {}
        for role in roles:
            roles_dict[role.index] = {arg.name:[arg.name,arg.range.start, arg.range.end] for arg in role.arguments}
        return roles_dict

    '''句法分析---为句子中的每个词语维护一个保存句法依存儿子节点的字典'''
    def build_parse_child_dict(self, words, postags, arcs):
        child_dict_list = []
        format_parse_list = []
        for index in range(len(words)):
            child_dict = dict()
            for arc_index in range(len(arcs)):
                if arcs[arc_index].head == index+1:   #arcs的索引从1开始
                    if arcs[arc_index].relation in child_dict:
                        child_dict[arcs[arc_index].relation].append(arc_index)
                    else:
                        child_dict[arcs[arc_index].relation] = []
                        child_dict[arcs[arc_index].relation].append(arc_index)
            child_dict_list.append(child_dict)
        rely_id = [arc.head for arc in arcs]  # 提取依存父节点id
        relation = [arc.relation for arc in arcs]  # 提取依存关系
        heads = ['Root' if id == 0 else words[id - 1] for id in rely_id]  # 匹配依存父节点词语
        for i in range(len(words)):
            # ['ATT', '李克强', 0, 'nh', '总理', 1, 'n']
            a = [relation[i], words[i], i, postags[i], heads[i], rely_id[i]-1, postags[rely_id[i]-1]]
            format_parse_list.append(a)

        return child_dict_list, format_parse_list

    '''parser主函数'''
    def parser_main(self, sentence):
        words = list(self.segmentor.segment(sentence))
        postags = list(self.postagger.postag(words))
        arcs = self.parser.parse(words, postags)
        child_dict_list, format_parse_list = self.build_parse_child_dict(words, postags, arcs)
        roles_dict = self.format_labelrole(words, postags)
        return words, postags, child_dict_list, roles_dict, format_parse_list
    def sentence_splitter(self,sentence='你好，你觉得这个例子从哪里来的？当然还是直接复制官方文档'):
        sents = SentenceSplitter.split(sentence) # 分句
        return (list(sents))
        


if __name__ == '__main__':
    mongo_con=MongoClient('172.20.66.56', 27017)
    db=mongo_con.Causal_event
    collection=db.forum50_articles_anaysis
    parse = LtpParser()
    path = r'E:\\Causal_events\\sina_articles_causality_extract\\'
    #sentence="我爱你,中国"
    files = os.listdir(path)
    #print(files)
    for file in files :
        pathname = os.path.join(path, file)
        print(file)
        #准确获取一个txt的位置，利用字符串的拼接
        txt_path = pathname
        #把结果保存了在contents中
        causality_extract=pd.read_csv(open(txt_path,'rb'))
        causality_extract=causality_extract.drop_duplicates(subset=['原因','结果'])
        biglist=[]
        for index,i in causality_extract.iterrows():
            yuanyin=i['原因'].replace('‘','，')
            jieguo=i['结果'].replace('‘','，') 
            tag=i['标签'] 
            word_yuanyin, postag_yuanyin= parse.parser_main(yuanyin)
            print(word_yuanyin,postag_yuanyin)
            word_jieguo, postag_jieguo= parse.parser_main(jieguo)
            list1=['sina经济论坛',file,yuanyin,str(word_yuanyin).replace('[','').replace(']',''), str(postag_yuanyin).replace(',', '').replace('[','').replace("'", '').replace(']','').strip(),jieguo,str(word_jieguo).replace('[','').replace(']',''), str(postag_jieguo).replace(',', '').replace('[','').replace("'", '').replace(']','').strip(),tag]
            biglist.append(list1)                                                                                                                                                                                                                                                                                                
        name=['栏目','文件名','原因句','原因句分词结果','原因句词性标注','结果句','结果句分词结果','结果句词性标注','标签']
        article_anaysis=pd.DataFrame(columns=name,data=biglist)
        if(article_anaysis.size>0):
            collection.insert(json.loads(article_anaysis.T.to_json()).values())
            article_anaysis.to_csv('E:\\Causal_events\\sina_articles_anaysis\\'+file,encoding='utf-8') 
    mongo_con.close() 