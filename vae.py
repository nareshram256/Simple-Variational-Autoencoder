import argparse
import numpy as np
import os
from utils_vae import sigmoid, lrelu, tanh, img_tile, mnist_reader, relu, BCE_loss

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--devid", type=int, default=-1)
    parser.add_argument("--epoch", type=int, default=40)
    parser.add_argument("--nz", type=int, default=20)
    parser.add_argument("--layersize", type=int, default=400)
    parser.add_argument("--alpha", type=float, default=1)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--bsize", type=int, default=64)
    return parser.parse_args()

args = parse_args()

class VAE():
    def __init__(self, numbers):
        
        self.numbers = numbers

        self.epochs = args.epoch
        self.batch_size = args.bsize
        self.learning_rate = args.lr
        self.decay = 0.001
        self.nz = args.nz
        self.layersize = args.layersize

        self.img_path = "./images"
        if not os.path.exists(self.img_path):
                os.makedirs(self.img_path)
        
        # Xavier initialization is used to initialize the weights
        # https://theneuralperspective.com/2016/11/11/weights-initialization/
        # init encoder weights
        self.e_W0 = np.random.randn(784, self.layersize).astype(np.float32) * np.sqrt(2.0/(784))
        self.e_b0 = np.zeros(self.layersize).astype(np.float32)

        self.e_W_mu = np.random.randn(self.layersize, self.nz).astype(np.float32) * np.sqrt(2.0/(self.layersize))
        self.e_b_mu = np.zeros(self.nz).astype(np.float32)
        
        self.e_W_logvar = np.random.randn(self.layersize, self.nz).astype(np.float32) * np.sqrt(2.0/(self.layersize))
        self.e_b_logvar = np.zeros(self.nz).astype(np.float32)

        # init decoder weights 
        self.d_W0 = np.random.randn(self.nz, self.layersize).astype(np.float32) * np.sqrt(2.0/(self.nz))
        self.d_b0 = np.zeros(self.layersize).astype(np.float32)
        
        self.d_W1 = np.random.randn(self.layersize, 784).astype(np.float32) * np.sqrt(2.0/(self.layersize))
        self.d_b1 = np.zeros(784).astype(np.float32)
        
        # init sample
        self.sample_z = 0
        
    def encoder(self, img):
        #self.e_logvar : log variance 
        #self.e_mean : mean

        self.e_input = np.reshape(img, (self.batch_size,-1))
    
        self.e_h0_l = self.e_input.dot(self.e_W0) + self.e_b0
        self.e_h0_a = lrelu(self.e_h0_l)
    		
        self.e_logvar = self.e_h0_a.dot(self.e_W_logvar) + self.e_b_logvar
        self.e_mu = self.e_h0_a.dot(self.e_W_mu) + self.e_b_mu
    
        return self.e_mu, self.e_logvar
    
    def decoder(self, z):
        #self.d_out : reconstruction image 28x28
		
        #probably not necessary
        self.z = np.reshape(z, (self.batch_size, self.nz))
        
        self.d_h0_l = self.z.dot(self.d_W0) + self.d_b0		
        self.d_h0_a = relu(self.d_h0_l)

        self.d_h1_l = self.d_h0_a.dot(self.d_W1) + self.d_b1
        self.d_h1_a = sigmoid(self.d_h1_l)

        self.d_out = np.reshape(self.d_h1_a, (self.batch_size, 28, 28, 1))

        return self.d_out
    
    def forward(self, x):
        #Encode
        mu, logvar = self.encoder(x)
        
        #use reparameterization trick to sample from gaussian
        self.sample_z = mu + np.exp(logvar * .5) * np.random.standard_normal(size=(self.batch_size, self.nz))
        
        return self.decoder(self.sample_z), mu, logvar
    
    def backward(self, x, out):
        ########################################
        #Calculate gradients from reconstruction
        ########################################
        y = np.reshape(x, (self.batch_size, -1))
        out = np.reshape(out, (self.batch_size, -1))
        
        #Calculate decoder gradients
        #Left side term
        dL_l = y * (1 / out)
        dsig = sigmoid(self.d_h1_l, derivative=True)
        dL_dsig_l = dL_l * dsig
        
        drelu = relu(self.d_h0_l, derivative=True)
        
        dW1_d_l = np.matmul(np.expand_dims(dL_dsig_l, axis=-1), np.expand_dims(drelu, axis=1))
        db1_d_l = dL_dsig_l 
        
        db0_d_l = dL_dsig_l.dot(self.d_W1.T) * drelu
        dW0_d_l = np.matmul(np.expand_dims(self.sample_z, axis=-1), np.expand_dims(db0_d_l, axis=1))
        
        #Right side term
        dL_r = (1 - y) * (1 / (1 - out)) # Need to check
        dL_dsig_r = dL_r * dsig
        
        dW1_d_r = np.matmul(np.expand_dims(dL_dsig_r, axis=-1), np.expand_dims(drelu, axis=1))
        db1_d_r = dL_dsig_r
        
        db0_d_r = dL_dsig_r.dot(self.d_W1.T) * drelu
        dW0_d_r = np.matmul(np.expand_dims(self.sample_z, axis=-1), np.expand_dims(db0_d_r, axis=1))
        
        # Combine gradients for decoder
        grad_d_W0 = dW0_d_l + dW0_d_r
        grad_d_b0 = db0_d_l + db0_d_r
        grad_d_W1 = dW1_d_l + dW1_d_r
        grad_d_b1 = db1_d_l + db1_d_r
        
        #Calculate encoder gradients from reconstruction
        #Left side term
        d_b_mu  = db0_d_l.dot(self.d_W0.T)
        d_W_mu = np.matmul(np.expand_dims(self.e_h0_a, axis=-1), np.expand_dims(d_b_mu, axis=1))
        
        db0_e_l = d_b_mu.dot(self.e_W_mu.T) * lrelu(self.e_h0_l, derivative=True)
        dW0_e_l = np.matmul(np.expand_dims(y, axis=-1), np.expand_dims(db0_e_l, axis=1)) 
        
        d_b_logvar = d_b_mu * np.exp(self.e_logvar * .5) * .5
        d_W_logvar = np.matmul(np.expand_dims(self.e_h0_a, axis=-1), np.expand_dims(d_b_logvar, axis=1))
        
        db0_e_l_2 = d_b_logvar.dot(self.e_W_logvar.T) * lrelu(self.e_h0_l, derivative=True)
        dW0_e_l_2 = np.matmul(np.expand_dims(y, axis=-1), np.expand_dims(db0_e_l_2, axis=1)) 
        
        #Right side term
        #NEED TO FILL!!!
        
        
        ########################################
        #Calculate encoder gradients from K-L
        ########################################
        
        #KL = sum(-.5 -.5l + .5m^2 +.5 e^l)
        dKL_W_log = -.5 *(self.e_h0_a[..., None]  - np.matmul(np.expand_dims(self.e_h0_a, axis=-1), np.expand_dims(np.exp(self.e_logvar), axis=1)))  #64 x 400 x 20        
        
        #recalculated with frobenius product
        dKL_W_log_2 = .5 * (np.exp(self.e_logvar) - 1)
        dKL_W_log_2 = np.matmul(np.expand_dims(self.e_h0_a, axis= -1), np.expand_dims(dKL_W_log_2, axis= 1))
        print(dKL_W_log.shape)
        print(dKL_W_log_2.shape)
        print(np.array_equal(dKL_W_log, dKL_W_log_2))
        raise Exception()
        
        dKL_b_log = -.5 * (1 - np.exp(self.e_logvar))
        
        
        dlrelu = lrelu(self.e_h0_l, derivative=True)
#        dKL_e_W0 = np.matmul(np.expand_dims(dlrelu, axis=1), self.e_W_logvar)
#        dKL_e_W0 = dKL_e_W0.T[..., None] * y[..., None]
#        print(dKL_e_W0.shape)
        
        #print(np.exp(self.e_logvar).shape)
        
        #m^2 term
        dKL_W_m = -.5 * (2 * np.matmul(np.expand_dims(self.e_h0_a, axis=-1), np.expand_dims(self.e_mu, axis=1)))
        dKL_b_m = -.5 * (2 * self.e_mu)
        
        
        
        raise Exception()
        
        

        
        # Update all weights
        for idx in range(self.batch_size):
            # Encoder Weights
#            self.e_W0 = self.e_W0 - self.learning_rate*grad_e_W0[idx]
#            self.e_b0 = self.e_b0 - self.learning_rate*grad_e_b0[idx]
#    
#            self.e_W_mu = self.e_W_mu - self.learning_rate*grad_e_W_mu[idx]
#            self.e_b_mu = self.e_b_mu - self.learning_rate*grad_e_b_mu[idx]
#            
#            self.e_W_logvar = self.e_W_logvar - self.learning_rate*grad_e_W_logvar[idx]
#            self.e_b_logvar = self.e_b_logvar - self.learning_rate*grad_e_b_logvar[idx]
#    
#            # Decoder Weights
#            self.d_W0 = self.d_W0 - self.learning_rate*grad_d_W0[idx]
#            self.d_b0 = self.d_b0 - self.learning_rate*grad_d_b0[idx]
#            
#            self.d_W1 = self.d_W1 - self.learning_rate*grad_d_W1[idx]
#            self.d_b1 = self.d_b1 - self.learning_rate*grad_d_b1[idx]
            pass
    
    def train(self):
        
        #Read in training data
        trainX, _, train_size = mnist_reader(self.numbers)
        np.random.shuffle(trainX)
        
        #set batch indices
        batch_idx = train_size//self.batch_size
        
        total_loss = 0
        total_kl = 0
        total = 0
        
        for epoch in range(self.epochs):
            for idx in range(batch_idx):
                # prepare batch and input vector z
                train_batch = trainX[idx*self.batch_size:idx*self.batch_size + self.batch_size]
                #ignore batch if there are insufficient elements 
                if train_batch.shape[0] != self.batch_size:
                    break

                ################################
                #		Forward Pass
                ################################
                
                out, mu, logvar = self.forward(train_batch)
                
                # Reconstruction Loss
                rec_loss = BCE_loss(out, train_batch)
                
                #K-L Divergence
                kl = -0.5 * np.sum(1 + logvar - np.power(mu, 2) - np.exp(logvar))
                
                loss = rec_loss + kl
                loss = loss / self.batch_size
                
                #Loss Recordkeeping
                total_loss += rec_loss / self.batch_size
                total_kl += kl / self.batch_size
                total += 1

                ################################
                #		Backward Pass
                ################################
                # for every result in the batch
                # calculate gradient and update the weights using Adam
                self.backward(train_batch, out)	


               #show res images as tile
                #if you don't want to see the result at every step, comment line below
                #img_tile(np.array(fake_img), self.img_path, epoch, idx, "res", False)
                #self.img = fake_img

                #print("Epoch [%d] Step [%d] G Loss:%.4f D Loss:%.4f Real Ave.: %.4f Fake Ave.: %.4f lr: %.4f"%(
                #        epoch, idx, np.mean(g_loss), np.mean(d_loss), np.mean(d_real_output), np.mean(d_fake_output), self.learning_rate))
                
                #update learning rate every epoch
                #self.learning_rate = self.learning_rate * (1.0/(1.0 + self.decay*epoch))
                
                #save image result every epoch
                #img_tile(np.array(self.img), self.img_path, epoch, idx, "res", True)


if __name__ == '__main__':

    numbers = [1]
    model = VAE(numbers)
    model.train()
    