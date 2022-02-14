import importlib_metadata
import pytorch_lightning as pl
from ...layers import CRF, SimpleDense
import torch
from ...metrics.chunk import ChunkF1, get_entities
from transformers import BertModel, BertTokenizer
import torch.nn as nn
from ...utils.preprocessing import fine_grade_tokenize

class BertCRF(pl.LightningModule):
    def __init__(self,
                 hidden_size: int,
                 lr: float,
                 weight_decay: float,
                 dropout: float,
                 **data_params):
        super().__init__()
        self.save_hyperparameters()
        self.label2id = data_params['label2id']
        self.id2label = {id: label for label, id in self.label2id.items()}

        self.bert = BertModel.from_pretrained(data_params['pretrained_dir'] + data_params['pretrained_model'])

        self.classifier = SimpleDense(
            input_size=self.bert.config.hidden_size, 
            hidden_size=hidden_size, 
            output_size=len(self.label2id))

        self.crf = CRF(len(self.label2id))

        self.tokenizer = BertTokenizer.from_pretrained(data_params['pretrained_dir'] + data_params['pretrained_model'])


        self.train_f1 = ChunkF1()
        self.val_f1 = ChunkF1()
        self.test_f1 = ChunkF1()

        

    def forward(self, inputs, label_ids=None):
        last_hidden_state = self.bert(**inputs).last_hidden_state
        emissions = self.classifier(last_hidden_state)
        mask = inputs['attention_mask'].gt(0)
        if label_ids is not None :
            loss = self.crf(emissions, label_ids, mask=mask) * (-1)
            pred_ids= self.crf.decode(emissions, mask=mask)
            return loss, pred_ids
        else :
            return self.crf.decode(emissions, mask=mask)


    def shared_step(self, batch):
        inputs = batch['inputs']
        label_ids = batch['label_ids']
        #将label padding部分改为-1 
        label_ids[label_ids==self.hparams.label_pad_id] = -1
        loss, pred_ids = self(inputs, label_ids=label_ids)
        pred_labels = []
        for ids in pred_ids:
            pred_labels.append([self.id2label[id] for id in ids])

        true_labels = []
        for i in range(len(label_ids)):
            indice = torch.where(label_ids[i] >= 0)
            ids = label_ids[i][indice].tolist()
            true_labels.append([self.id2label[id] for id in ids])
        return loss, pred_labels, true_labels
        

    
    def training_step(self, batch, batch_idx):
        loss, pred_labels, true_labels = self.shared_step(batch)
        self.train_f1(pred_labels, true_labels)
        self.log('train/f1', self.train_f1, on_step=True, on_epoch=True, prog_bar=True)
        return {'loss':loss}


    def validation_step(self, batch, batch_idx):
        loss, pred_labels, true_labels = self.shared_step(batch)
        self.val_f1(pred_labels, true_labels)
        self.log('val/f1', self.val_f1, on_step=False, on_epoch=True, prog_bar=True)
        return {'loss':loss}

    
    def test_step(self, batch, batch_idx):
        loss, pred_labels, true_labels = self.shared_step(batch)
        self.test_f1(pred_labels, true_labels)
        self.log('test/f1', self.test_f1, on_step=False, on_epoch=True, prog_bar=True)
        return {'loss':loss}



    def configure_optimizers(self):
        no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
        grouped_parameters = [
            {'params': [p for n, p in self.bert.named_parameters() if not any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr, 'weight_decay': self.hparams.weight_decay},
            {'params': [p for n, p in self.bert.named_parameters() if any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr, 'weight_decay': 0.0},
            {'params': [p for n, p in self.classifier.named_parameters() if not any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr * 5, 'weight_decay': self.hparams.weight_decay},
            {'params': [p for n, p in self.classifier.named_parameters() if any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr * 5, 'weight_decay': 0.0},
            {'params': self.crf.parameters(), 'lr': self.hparams.lr * 500, 'weight_decay': self.hparams.weight_decay}
        ]
        self.optimizer = torch.optim.Adam(grouped_parameters, lr=self.hparams.lr)
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, lambda epoch: 1.0 / (epoch + 1.0))
        return [self.optimizer], [self.scheduler]


    def predict(self, text: str):
        tokens = fine_grade_tokenize(text, self.tokenizer)
        inputs = self.tokenizer.encode_plus(
            tokens,
            is_pretokenized=True,
            add_special_tokens=True,
            return_tensors='pt')
        outputs = self(inputs)
        labels = [self.id2label[id] for id in outputs[0]]
        ents = get_entities(seq=labels[1:-1])    #去掉cls sep 位置
        new_ents = []
        for ent in ents:
            new_ents.append([ent[1], ent[2], ent[0], text[ent[1]:ent[2]+1]])
        return new_ents
        
