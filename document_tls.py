from __future__ import division
from __future__ import print_function
import argparse
import chainer
import chainer.functions as F
from chainer import serializers
from chainer import variable
from ipdb import set_trace

import numpy as np
import six
import six.moves.cPickle as pickle

import sys
sys.path.append("./mylink")
sys.path.append("./_models")

import rnndec
import rnnenc
import middle
import ext_classifier as ec
import MeCab


parser = argparse.ArgumentParser()
parser.add_argument('--batchsize', '-b', type=int, default=64,
                    help='Number of examples in each mini batch')
parser.add_argument('--unit', '-u', type=int, default=1000,
                    help='Number of LSTM units in each layer')
parser.add_argument('--emb_unit', '-eu', type=int, default=100,
                    help='Number of LSTM units in each layer')
parser.add_argument('--gpu', '-g', type=int, default=-1,
                    help='GPU ID (negative value indicates CPU)')
parser.add_argument('--length', type=int, default=20,
                    help='length of the generated text')
parser.add_argument('--dir', '-d', default="",
                    help='Which result data')
parser.add_argument('--wdir', '-wd', default="",
                    help='Which result data')
parser.add_argument('--input', '-i', default="",
                    help='Which result data')
parser.add_argument('--output', '-o', default="",
                    help='Which result data')

parser.set_defaults(test=False)
args = parser.parse_args()

with open("%s/source.vocab" % args.wdir, "rb") as f:
    source_vocab = pickle.load(f, encoding='bytes')

with open("%s/target.vocab" % args.wdir, "rb") as f:
    target_vocab = pickle.load(f, encoding='bytes')


def softmax(x):
    e = numpy.exp(x - numpy.max(x))  # prevent overflow
    if e.ndim == 1:
        return e / numpy.sum(e, axis=0)
    else:
        return e / numpy.array([numpy.sum(e, axis=1)]).T

enc = rnnenc.RNNEncoder(len(source_vocab),
                        args.emb_unit, args.unit, args.gpu, train=False)
dec = rnndec.RNNDecoder(len(target_vocab),
                        args.emb_unit, args.unit, args.batchsize,
                        args.gpu, train=False)
middle_c = middle.MiddleC(args.unit, train=False)

enc_model = ec.EncClassifier(enc)
dec_model = ec.DecClassifier(dec)


if args.dir:
    print('Load model from %s/dec.model' % args.dir)
    serializers.load_npz("%s/dec.model" % args.dir, dec_model)
    print('Load model from %s/enc.model' % args.dir)
    serializers.load_npz("%s/enc.model" % args.dir, enc_model)
    print('Load model from %s/middle.model' % args.dir)
    serializers.load_npz("%s/middle.model" % args.dir, middle_c)

mt = MeCab.Tagger("-Owakati")
unk_id = source_vocab["<unk>"]

source_embeddings = {}
target_embeddings = {}
for word, ID in source_vocab.items():
    source_embeddings[word] = enc.emdeddings(ID)
set_trace()
for word, ID in target_vocab.items():
    target_embeddings[word] = dec.emdeddings(ID)

out = []
with open("%s" % args.input, "r") as f:
    for line in f:
        enc.reset_state()
        dec.reset_state()

        inputs = line.strip().split()
        inputs = inputs[::-1]
        inputs.append("<eos>")
        ids = [source_vocab.get(word, unk_id) for word in inputs]
        rev_source_vocab = {v:k for k, v in source_vocab.items()}
        for _id in ids:
            #print(rev_source_vocab[_id])
            enc_model.predictor(np.array([_id], dtype=np.int32))

        middle_c(enc_model.predictor.l1.h)
        dec_model.predictor.set_initial_l1(middle_c)

        prev_y = np.array([-1], dtype=np.int32)
        rev_target_vocab = {v:k for k, v in target_vocab.items()}

        tmp_out = []
        for i in six.moves.range(args.length):
            _prob = dec_model.predictor(prev_y, middle_c, 1)
            prob = F.softmax(_prob)
            wid = prob.data.argmax(1)[0]

            if rev_target_vocab[wid] == '<eos>':
                break
            else:
                tmp_out.append(rev_target_vocab[wid])

            prev_y = np.array([wid], dtype=np.int32)
        tmp_out.append('\n')
        out.append(tmp_out)

with open("%s/translated" % args.output, "w") as f:
    for line in out:
        f.write(" ".join(line))

with open("%s/source_embeddings" % args.output, "wb") as f:
    pickle.dump(source_embeddings, f)
with open("%s/target_embeddings" % args.output, "wb") as f:
    pickle.dump(target_embeddings, f)
