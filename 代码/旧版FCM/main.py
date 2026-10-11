import numpy as np
import matplotlib.pyplot as plt

def FCM_train(X, n_centers, m, max_iter=100, theta = 1e-5 , seed=0):
    
    rng = np.random.RandomState(seed) #创建随机数生成器并设置种子(seed)，保证结果可重复。
    N,D = np.shape(X) #获取X的行数N和列数D

    U = rng.uniform(size=(N, n_centers)) #生成N行n_centers列的随机隶属度矩阵(0-1均匀分布)
    U = U/np.sum(U, axis=1, keepdims=True) #归一化使每行和为1
                 
    for i in range(max_iter): #迭代更新U和centers直到收敛
        print(i)
        U_old = U.copy() #保存旧的隶属度矩阵用于收敛判断
        centers = FCM_getCenters(U,X,m) #根据当前U计算新的聚类中心
        U = FCM_getU(X, centers, m)  #根据新中心更新隶属度矩阵

        if np.linalg.norm(U - U_old) < theta: #如果U的变化小于阈值则停止迭代
            break

    return centers, U

def FCM_getCenters(U, X, m):

    N,D = np.shape(X)
    N,C = np.shape(U)

    um = U ** m

    tile_X = np.tile(np.expand_dims(X,1), [1,C,1])
    tile_um = np.tile(np.expand_dims(um, -1),[1, 1, D])
    temp = tile_X*tile_um

    new_C = np.sum(temp, axis=0)/np.expand_dims(np.sum(um, axis=0), axis=-1)

    return new_C

def FCM_getU(X, Centers, m):
    N,D = np.shape(X)
    C,D = np.shape(Centers)

    temp = FCM_dish(X, Centers) ** float(2/(m-1))

    tile_temp = np.tile(np.expand_dims(temp,1),[1,C,1])
    denominator_ = np.expand_dims(temp,-1)/tile_temp

    return 1/np.sum(denominator_,axis=-1)

def FCM_dish(X, Centers):
    
    N,D = np.shape(X)
    C,D = np.shape(Centers)

    tile_x = np.tile(np.expand_dims(X,1),[1,C,1])
    tile_centers = np.tile(np.expand_dims(Centers, axis=0),[N,1,1])

    dist = np.sum((tile_x-tile_centers)**2,axis=-1)

    return np.sqrt(dist)

def FCM_getClass(U):    return np.argmax(U, axis=-1)
def FCM_partition_coefficient(U):  return np.mean(U ** 2)
def FCM_partition_entropy_coefficient(U): return -np.mean(U * np.log2(U))

X = np.concatenate((
    np.random.normal((0, 0), size=(10000, 2)),
    # np.random.normal((-1.5,-1.5), size=(5000, 2)),

))

centers,U = FCM_train(X,3,2,max_iter=100, theta = 1e-5 , seed=0)

labels = FCM_getClass(U)

print(labels)

f, axes = plt.subplots(1, 2, figsize=(11,5))
axes[0].scatter(X[:,0],X[:,1],alpha=.1)
axes[1].scatter(X[:,0],X[:,1],c=labels,alpha=.1)
axes[1].scatter(centers[:,0], centers[:,1], marker="+", s=500, c="w")

plt.show()  
