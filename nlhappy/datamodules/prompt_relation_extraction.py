import pytorch_lightning as pl
from ..utils.make_datamodule import prepare_data_from_oss, align_char_span
from torch.utils.data import DataLoader
from datasets import load_from_disk
from transformers import AutoConfig, AutoTokenizer
import os
import torch
from typing import Dict
import logging

log = logging.getLogger()



class PromptRelationExtractionDataModule(pl.LightningDataModule):
    def __init__(self,
                dataset: str,
                plm: str,
                max_length: int,
                batch_size: int,
                pin_memory: bool=False,
                num_workers: int=0,
                dataset_dir: str ='./datasets/',
                plm_dir: str = './plms/') :
        """基于模板提示的文本片段抽取数据模块

        Args:
            dataset (str): 数据集名称
            plm (str): 预训练模型名称
            max_length (int): 文本最大长度
            batch_size (int): 批次大小
            pin_memory (bool, optional): 锁页内存. Defaults to True.
            num_workers (int, optional): 多进程. Defaults to 0.
            dataset_dir (str, optional): 数据集目录. Defaults to './datasets/'.
            plm_dir (str, optional): 预训练模型目录. Defaults to './plms/'.
        """
        super().__init__()
        self.save_hyperparameters()
        
        
    def prepare_data(self) -> None:
        
        prepare_data_from_oss(dataset=self.hparams.dataset,
                              plm=self.hparams.plm,
                              dataset_dir=self.hparams.dataset_dir,
                              plm_dir=self.hparams.plm_dir)
        
    def setup(self, stage: str) -> None:
        dataset_path = os.path.join(self.hparams.dataset_dir, self.hparams.dataset)
        self.dataset = load_from_disk(dataset_path)
        plm_path = os.path.join(self.hparams.plm_dir, self.hparams.plm)
        self.tokenizer = AutoTokenizer.from_pretrained(plm_path)
        self.hparams['vocab'] = dict(sorted(self.tokenizer.vocab.items(), key=lambda x: x[1]))
        trf_config = AutoConfig.from_pretrained(plm_path)
        self.hparams['trf_config'] = trf_config
        self.dataset.set_transform(transform=self.transform)
        
    def transform(self, example) -> Dict:
        batch_text = example['text']
        batch_triples = example['triples']
        batch_prompts = example['prompts']
        batch_inputs = {'input_ids': [], 'attention_mask': [], 'token_type_ids': [], 'so_ids': [], 'head_ids': [], 'tail_ids': []}
        for i, text in enumerate(batch_text):
            prompt = batch_prompts[i]
            inputs = self.tokenizer(
                text, 
                prompt,
                padding='max_length',  
                max_length=self.hparams.max_length,
                truncation=True,
                return_offsets_mapping=True)
            batch_inputs['input_ids'].append(inputs['input_ids'])
            batch_inputs['attention_mask'].append(inputs['attention_mask'])
            batch_inputs['token_type_ids'].append(inputs['token_type_ids'])
            offset_mapping = inputs['offset_mapping']
            bias = 0
            for index in range(len(offset_mapping)):
                if index == 0:
                    continue
                mapping = offset_mapping[index]
                if mapping[0] == 0 and mapping[1] == 0 and bias == 0:
                    bias = index
                if mapping[0] == 0 and mapping[1] == 0:
                    continue
                offset_mapping[index][0] += bias
                offset_mapping[index][1] += bias
            so_ids = torch.zeros(2, self.hparams.max_length, self.hparams.max_length)
            # span_ids = torch.zeros(len(self.hparams['s_label2id']), self.hparams.max_length, self.hparams.max_length)
            head_ids = torch.zeros(1, self.hparams.max_length, self.hparams.max_length)
            tail_ids = torch.zeros(1, self.hparams.max_length, self.hparams.max_length)
            triples = batch_triples[i]
            for triple in triples:
                #加1是因为有cls
                try:
                    sub_start = triple['subject']['offset'][0] + bias
                    sub_end = triple['subject']['offset'][1] + bias -1
                    sub_start, sub_end = align_char_span((sub_start, sub_end), offset_mapping)
                    obj_start = triple['object']['offset'][0] + bias
                    obj_end = triple['object']['offset'][1] + bias -1
                    obj_start, obj_end = align_char_span((obj_start,obj_end), offset_mapping)
                    so_ids[0][sub_start][sub_end] = 1
                    so_ids[1][obj_start][obj_end] = 1
                    head_ids[0][sub_start][obj_start] = 1
                    tail_ids[0][sub_end][obj_end] = 1
                except:
                    log.warning('char offset align to token offset failed')
                    pass
            batch_inputs['so_ids'].append(so_ids)
            batch_inputs['head_ids'].append(head_ids)
            batch_inputs['tail_ids'].append(tail_ids)
        batch_inputs['so_ids'] = torch.stack(batch_inputs['so_ids'], dim=0)
        batch_inputs['head_ids'] = torch.stack(batch_inputs['head_ids'], dim=0)
        batch_inputs['tail_ids'] = torch.stack(batch_inputs['tail_ids'], dim=0)
        batch = dict(zip(batch_inputs.keys(), map(torch.tensor, batch_inputs.values())))
        return batch
            

    def train_dataloader(self):
        '''
        返回训练集的DataLoader.
        '''
        return DataLoader(
            dataset= self.dataset['train'], 
            batch_size=self.hparams.batch_size, 
            num_workers=self.hparams.num_workers, 
            pin_memory=self.hparams.pin_memory,
            shuffle=True)
        
    def val_dataloader(self):
        '''
        返回验证集的DataLoader.
        '''
        return DataLoader(
            dataset=self.dataset['validation'], 
            batch_size=self.hparams.batch_size, 
            num_workers=self.hparams.num_workers, 
            pin_memory=self.hparams.pin_memory,
            shuffle=False)

    def test_dataloader(self):
        '''
        返回验证集的DataLoader.
        '''
        return DataLoader(
            dataset=self.dataset['test'], 
            batch_size=self.hparams.batch_size, 
            num_workers=self.hparams.num_workers, 
            pin_memory=self.hparams.pin_memory,
            shuffle=False)