# coding=utf-8
# Copyright (c) 2019 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import logging

import tensorflow.compat.v1 as tf
import tensorflow_addons as tfa
from tensorflow.keras.layers import Activation
from tensorflow.keras.layers import BatchNormalization
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import Dropout
from tensorflow.keras.layers import Layer
from tensorflow.keras.layers import LayerNormalization

from ludwig.models.modules.initializer_modules import get_initializer

logger = logging.getLogger(__name__)


def fc_layer(inputs, in_count, out_count,
             activation='relu', norm=None,
             is_training=True, weights=None, biases=None,
             dropout=False, dropout_rate=None,
             initializer=None, regularizer=None):
    if weights is None:
        if initializer is not None:
            initializer_obj = get_initializer(initializer)
            weights = tf.get_variable(
                'weights',
                initializer=initializer_obj([in_count, out_count]),
                regularizer=regularizer
            )
        else:
            if activation == 'relu':
                initializer = get_initializer('he_uniform')
            elif activation == 'sigmoid' or activation == 'tanh':
                initializer = get_initializer('glorot_uniform')
            # if initializer is None, tensorFlow seems to be using
            # a glorot uniform initializer
            weights = tf.get_variable(
                'weights',
                [in_count, out_count],
                regularizer=regularizer,
                initializer=initializer
            )

    logger.debug('  fc_weights: {}'.format(weights))

    if biases is None:
        biases = tf.get_variable('biases', [out_count],
                                 initializer=tf.constant_initializer(0.01))
    logger.debug('  fc_biases: {}'.format(biases))

    hidden = tf.matmul(inputs, weights) + biases

    if norm is not None:
        if norm == 'batch':
            hidden = tfa.layers.batch_norm(hidden,
                                           is_training=is_training)
        elif norm == 'layer':
            hidden = tfa.layers.layer_norm(hidden)

    if activation:
        hidden = getattr(tf.nn, activation)(hidden)

    if dropout and dropout_rate is not None:
        hidden = tf.layers.dropout(hidden, rate=dropout_rate,
                                   training=is_training)
        logger.debug('  fc_dropout: {}'.format(hidden))

    return hidden


class FCStack(Layer):

    def __init__(
            self,
            layers=None,
            num_layers=1,
            default_fc_size=256,
            default_activation='relu',
            default_use_bias=True,
            default_norm=None,
            default_dropout_rate=0,
            default_weights_initializer='glorot_uniform',
            default_bias_initializer='zeros',
            default_weights_regularizer=None,
            default_bias_regularizer=None,
            # default_activity_regularizer=None,
            # default_weights_constraint=None,
            # default_bias_constraint=None,
    ):
        super(FCStack, self).__init__()

        if layers is None:
            self.layers = []
            for i in range(num_layers):
                self.layers.append({})
        else:
            self.layers = layers

        for layer in self.layers:
            if 'fc_size' not in layer:
                layer['fc_size'] = default_fc_size
            if 'activation' not in layer:
                layer['activation'] = default_activation
            if 'norm' not in layer:
                layer['norm'] = default_norm
            if 'dropout_rate' not in layer:
                layer['dropout_rate'] = default_dropout_rate
            if 'weights_initializer' not in layer:
                layer['weights_initializer'] = default_weights_initializer
            if 'weights_regularizer ' not in layer:
                layer['weights_regularizer '] = default_weights_regularizer

        self.stack = []

        for i, layer in enumerate(self.layers):
            with tf.variable_scope('fc_' + str(i)):
                self.stack.append(Dense(
                    layer['fc_size'],
                    kernel_initializer=layer['weights_initializer'],
                    kernel_regularizer=layer['weights_regularizer'],
                ))

                if layer['norm']:
                    if layer['norm'] == 'batch':
                        self.stack.append(BatchNormalization())
                    if layer['norm'] == 'layer':
                        self.stack.append(LayerNormalization())

                self.stack.append(Activation(layer['activation']))

                if layer['dropout_rate'] > 0:
                    self.stack.append(Dropout(layer['dropout_rate']))

                # logger.debug('  fc_{}: {}'.format(i, hidden))

    def build(
            self,
            input_shape,
    ):
        super(FCStack, self).build(input_shape)

    def call(self, inputs, training=None):
        hidden = inputs
        for layer in self.stack:
            hidden = layer(hidden, training=training)
        return hidden

    def compute_output_shape(self, input_shape):
        if self.stack:
            return self.stack[-1].compute_output_shape(input_shape)
        return input_shape
