import numpy as np
import torch
import matplotlib.pyplot as plt
import shutil
from torch import nn
from tqdm import tqdm

plt.switch_backend('agg')


def adjust_learning_rate(accelerator, optimizer, scheduler, epoch, args, printout=True):
    if args.lradj == 'type1':
        lr_adjust = {epoch: args.learning_rate * (0.5 ** ((epoch - 1) // 1))}
    elif args.lradj == 'type2':
        lr_adjust = {
            2: 5e-5, 4: 1e-5, 6: 5e-6, 8: 1e-6,
            10: 5e-7, 15: 1e-7, 20: 5e-8
        }
    elif args.lradj == 'type3':
        lr_adjust = {epoch: args.learning_rate if epoch < 3 else args.learning_rate * (0.9 ** ((epoch - 3) // 1))}
    elif args.lradj == 'PEMS':
        lr_adjust = {epoch: args.learning_rate * (0.95 ** (epoch // 1))}
    elif args.lradj == 'TST':
        lr_adjust = {epoch: scheduler.get_last_lr()[0]}
    elif args.lradj == 'constant':
        lr_adjust = {epoch: args.learning_rate}
    if epoch in lr_adjust.keys():
        lr = lr_adjust[epoch]
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr
        if printout:
            if accelerator is not None:
                accelerator.print('Updating learning rate to {}'.format(lr))
            else:
                print('Updating learning rate to {}'.format(lr))


class EarlyStopping:
    def __init__(self, accelerator=None, patience=7, verbose=True, delta=0, save_mode=True):
        self.accelerator = accelerator
        self.patience = patience
        self.verbose = verbose
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.val_loss_min = np.Inf
        self.delta = delta
        self.save_mode = save_mode

    def __call__(self, val_loss, model, path):
        score = -val_loss
        if self.best_score is None:
            self.best_score = score
            if self.save_mode:
                self.save_checkpoint(val_loss, model, path)
        elif score < self.best_score + self.delta:
            self.counter += 1
            if self.accelerator is None:
                print(f'EarlyStopping counter: {self.counter} out of {self.patience}')
            else:
                self.accelerator.print(f'EarlyStopping counter: {self.counter} out of {self.patience}')
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = score
            if self.save_mode:
                self.save_checkpoint(val_loss, model, path)
            self.counter = 0

    def save_checkpoint(self, val_loss, model, path):
        if self.verbose:
            if self.accelerator is not None:
                self.accelerator.print(
                    f'Validation loss decreased ({self.val_loss_min:.6f} --> {val_loss:.6f}).  Saving model ...')
            else:
                print(
                    f'Validation loss decreased ({self.val_loss_min:.6f} --> {val_loss:.6f}).  Saving model ...')
            
        if self.accelerator is not None:
            model = self.accelerator.unwrap_model(model)
            torch.save(model.state_dict(), path + '/' + 'checkpoint')
        else:
            torch.save(model.state_dict(), path + '/' + 'checkpoint')
        self.val_loss_min = val_loss

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class StandardScaler():
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def transform(self, data):
        return (data - self.mean) / self.std

    def inverse_transform(self, data):
        return (data * self.std) + self.mean

def adjustment(gt, pred):
    anomaly_state = False
    for i in range(len(gt)):
        if gt[i] == 1 and pred[i] == 1 and not anomaly_state:
            anomaly_state = True
            for j in range(i, 0, -1):
                if gt[j] == 0:
                    break
                else:
                    if pred[j] == 0:
                        pred[j] = 1
            for j in range(i, len(gt)):
                if gt[j] == 0:
                    break
                else:
                    if pred[j] == 0:
                        pred[j] = 1
        elif gt[i] == 0:
            anomaly_state = False
        if anomaly_state:
            pred[i] = 1
    return gt, pred


def cal_accuracy(y_pred, y_true):
    return np.mean(y_pred == y_true)


def del_files(dir_path):
    shutil.rmtree(dir_path)

import time 
def count_inf_time(args , model,  vali_loader, criterion, mae_metric , device):
    model.eval()
    with torch.no_grad():
        for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in tqdm(enumerate(vali_loader), disable=True):
            batch_x = batch_x.float().to(device)
            batch_x_mark = batch_x_mark.float().to(device)
            batch_y_mark = batch_y_mark.float().to(device)
            beg = time.time()
            model(batch_x, batch_x_mark, None, batch_y_mark)
            return time.time() - beg 
        
def perturb_sequence(batch_x , shuffle_type , patch_size = 16 , mask_ratio= 0.5  ):
    '''
        batch_x : shape [256, 336, 1]
        perturb time series input 
        sf_all : shuffle the whole sequnece 
        sf_half : shuffle first halp sequnece 
        ex-half : exchange first and second half 
    '''
    assert shuffle_type in ['sf_all' , 'sf_half' , 'ex_half' ,'sf_patchs' , 'masking']
    if shuffle_type == 'sf_all':
        perm = torch.randperm(batch_x.size(1))
        return batch_x[:, perm, :]
    if shuffle_type == 'sf_half':
        mid_point = batch_x.size(1) // 2
        pre_half = batch_x[:, :mid_point, :]
        post_half = batch_x[:, mid_point:, :]
        perm = torch.randperm(pre_half.size(1))
        shuffled_pre_half = pre_half[:, perm, :]
        return torch.cat((shuffled_pre_half, post_half), dim=1)
    if shuffle_type == 'ex_half':
        mid_point = batch_x.size(1) // 2
        pre_half = batch_x[:, :mid_point, :]
        post_half = batch_x[:, mid_point:, :]
        return torch.cat((post_half, pre_half), dim=1)
    if shuffle_type =='masking':
        input_length  = batch_x.size(1)
        num_to_mask = int(input_length * mask_ratio )
        mask_indices = torch.randperm(input_length)[:num_to_mask]
        masked_tensor = batch_x.clone()
        masked_tensor[:, mask_indices, :] = 0
        return masked_tensor
    if shuffle_type =='sf_patchs':
        num_patches= (batch_x.size(1)  // patch_size )
        shuffle_indices = torch.randperm(num_patches)
        shuffled_ts = [batch_x[:, i*patch_size:(i+1)*patch_size, :] for i in shuffle_indices]
        if  num_patches * patch_size < batch_x.size(1):
            shuffled_ts.append(batch_x[:, num_patches*patch_size:, :])
        return torch.cat(shuffled_ts , dim=1)
        
def eval_shuffle(args , model,  vali_loader, criterion, mae_metric , device):
    total_mae_loss = []
    total_mse_loss = []
    model.eval()
    is_first=True
    with torch.no_grad():
        shuffle_types = ['ori' , 'sf_all' , 'sf_half' , 'ex_half'  , 'masking']
        for shuffle_type in shuffle_types :
            print(shuffle_type) 
            maes = [] ;  mses = []
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in tqdm(enumerate(vali_loader), disable=True):
                batch_x = batch_x.float().to(device)
                batch_y = batch_y.float()
                
                batch_x_mark = batch_x_mark.float().to(device)
                batch_y_mark = batch_y_mark.float().to(device)
                
                if is_first : 
                    print(batch_x.shape , batch_y.shape)
                    is_first=False
                # [256, 336, 1]
                if shuffle_type != 'ori':
                    batch_x = perturb_sequence(batch_x , shuffle_type )
                    
                outputs = model(batch_x, batch_x_mark, None, batch_y_mark)
                
                f_dim = -1 if args.features == 'MS' else 0
                outputs = outputs[:, -args.pred_len:, f_dim:]
                batch_y = batch_y[:, -args.pred_len:, f_dim:].to(device)

                pred = outputs.detach()
                true = batch_y.detach()

                mae_loss = torch.mean(torch.abs(pred - true),axis=(1, 2))
                mse_loss = torch.mean((pred - true)**2,axis=(1, 2))
                maes.append(mae_loss.cpu().numpy())
                mses.append(mse_loss.cpu().numpy())
                
            total_mae_loss.append(np.mean(maes))
            total_mse_loss.append(np.mean(mses))
            
            print('mae' , total_mae_loss)
    return total_mae_loss , total_mse_loss

def eval_bs(args , model,  vali_loader, criterion, mae_metric , device):
    total_loss = []
    total_mae_loss = []
    total_mse_loss = []
    model.eval()
    mse_metric = nn.MSELoss()
    with torch.no_grad():
        for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in tqdm(enumerate(vali_loader), disable=True):
            batch_x = batch_x.float().to(device)
            batch_y = batch_y.float()
            
            batch_x_mark = batch_x_mark.float().to(device)
            batch_y_mark = batch_y_mark.float().to(device)
            
            # print(batch_x_mark.dtype)
            # for name, param in model.named_parameters():
            #     print(f"Parameter: {name}, Type: {param.dtype}")
            
            outputs = model(batch_x, batch_x_mark, None, batch_y_mark)

            f_dim = -1 if args.features == 'MS' else 0
            outputs = outputs[:, -args.pred_len:, f_dim:]
            batch_y = batch_y[:, -args.pred_len:, f_dim:].to(device)

            pred = outputs.detach()
            true = batch_y.detach()

            mae_loss = torch.mean(torch.abs(pred - true),axis=(1, 2))
            mse_loss = torch.mean((pred - true)**2,axis=(1, 2))
            
            total_mae_loss.append(mae_loss.cpu().numpy())
            total_mse_loss.append(mse_loss.cpu().numpy())
            
    total_mae_loss = np.array(total_mae_loss).reshape(-1,)
    total_mse_loss = np.array(total_mse_loss).reshape(-1,)
    print(total_mae_loss.shape , total_mse_loss.shape)
    
    return total_mae_loss , total_mse_loss 
    
def vali(args, accelerator, model, vali_data, vali_loader, criterion, mae_metric):
    total_loss = []
    total_mae_loss = []
    total_mse_loss = []
    model.eval()
    mse_metric = nn.MSELoss()
    with torch.no_grad():
        for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in tqdm(enumerate(vali_loader), disable=True):
            batch_x = batch_x.float().to(accelerator.device)
            batch_y = batch_y.float()
            
            batch_x_mark = batch_x_mark.float().to(accelerator.device)
            batch_y_mark = batch_y_mark.float().to(accelerator.device)

            # decoder input
            dec_inp = torch.zeros_like(batch_y[:, -args.pred_len:, :]).float()
            dec_inp = torch.cat([batch_y[:, :args.label_len, :], dec_inp], dim=1).float().to(
                accelerator.device)
            # encoder - decoder
            if args.use_amp:
                with torch.cuda.amp.autocast():
                    if args.output_attention:
                        outputs = model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                    else:
                        outputs = model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
            else:
                if args.output_attention:
                    outputs = model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                else:
                    outputs = model(batch_x, batch_x_mark, dec_inp, batch_y_mark)

            outputs, batch_y = accelerator.gather_for_metrics((outputs, batch_y))

            f_dim = -1 if args.features == 'MS' else 0
            outputs = outputs[:, -args.pred_len:, f_dim:]
            batch_y = batch_y[:, -args.pred_len:, f_dim:].to(accelerator.device)

            pred = outputs.detach()
            true = batch_y.detach()

            loss = criterion(pred, true)

            mae_loss = mae_metric(pred, true)
            mse_loss = mse_metric(pred, true)
            
            total_loss.append(loss.item())
            total_mae_loss.append(mae_loss.item())
            total_mse_loss.append(mse_loss.item())
            
    total_loss = np.average(total_loss)
    total_mae_loss = np.average(total_mae_loss)
    total_mse_loss = np.average(total_mse_loss)

    model.train()
    return total_loss, total_mae_loss , total_mse_loss 


def test(args, accelerator, model, train_loader, vali_loader, criterion):
    x, _ = train_loader.dataset.last_insample_window()
    y = vali_loader.dataset.timeseries
    x = torch.tensor(x, dtype=torch.float32).to(accelerator.device)
    x = x.unsqueeze(-1)
    
    model.eval()
    with torch.no_grad():
        B, _, C = x.shape
        dec_inp = torch.zeros((B, args.pred_len, C)).float().to(accelerator.device)
        dec_inp = torch.cat([x[:, -args.label_len:, :], dec_inp], dim=1)
        outputs = torch.zeros((B, args.pred_len, C)).float().to(accelerator.device)
        id_list = np.arange(0, B, args.eval_batch_size)
        id_list = np.append(id_list, B)
        for i in range(len(id_list) - 1):
            outputs[id_list[i]:id_list[i + 1], :, :] = model(
                x[id_list[i]:id_list[i + 1]],
                None,
                dec_inp[id_list[i]:id_list[i + 1]],
                None
            )
        accelerator.wait_for_everyone()
        outputs = accelerator.gather_for_metrics(outputs)
        f_dim = -1 if args.features == 'MS' else 0
        outputs = outputs[:, -args.pred_len:, f_dim:]
        pred = outputs
        true = torch.from_numpy(np.array(y)).to(accelerator.device)
        batch_y_mark = torch.ones(true.shape).to(accelerator.device)
        true = accelerator.gather_for_metrics(true)
        batch_y_mark = accelerator.gather_for_metrics(batch_y_mark)

        loss = criterion(x[:, :, 0], args.frequency_map, pred[:, :, 0], true, batch_y_mark)

    model.train()
    return loss


def load_content(args):
    if 'ETT' in args.data:
        file = 'ETT'
    else:
        file = args.data
    with open('./datasets/prompt_bank/{0}.txt'.format(file), 'r') as f:
        content = f.read()
    return content