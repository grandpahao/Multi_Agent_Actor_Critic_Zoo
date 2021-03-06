import IPython
import numpy as np
import tensorflow as tf

from .tfagent import TFAgent


class Actor(TFAgent):
    def __init__(self, n_ac, lr, test=False):
        super(Actor, self).__init__(n_ac, lr, test)
        self.update_target()

    def _build_net(self):
        if self.test:
            input_shape = [None, 4]
        else:
            input_shape = [None, 84, 84, 4]
        self.input = tf.placeholder(
            shape=input_shape, dtype=tf.float32, name='inputs')

        self.action_select = tf.placeholder(
            shape=[None], dtype=tf.int32, name='selected_action')
        self.advantage = tf.placeholder(
            shape=[None], dtype=tf.float32, name='advantage')

        with tf.variable_scope('actor_accurate'):
            fc1 = self._net(self.input, trainable=True)
            self.action = tf.contrib.layers.fully_connected(
                fc1, self.n_ac, trainable=True)
            self.action_prob = tf.nn.softmax(self.action)

        with tf.variable_scope('actor_target'):
            fc1_target = self._net(self.input, trainable=False)
            self.action_target = tf.contrib.layers.fully_connected(
                fc1_target, self.n_ac, trainable=False)
            self.target_action_prob = tf.nn.softmax(self.action_target)

        self.update_target_opr = self._update_target_opr()

        trainable_variables = tf.trainable_variables('actor_accurate')
        self.loss = self._eval_loss()
        self.train_opr = self.optimizer.minimize(
            self.loss,
            global_step=tf.train.get_global_step(),
            var_list=trainable_variables
        )

    def update(self, input_batch, action_batch, advantage_batch):
        _, actor_loss, actor_max_prob = self.sess.run(
            [
                self.train_opr,
                self.loss, tf.reduce_max(
                    self.target_action_prob, axis=1)
            ],
            feed_dict={
                self.input: input_batch,
                self.action_select: action_batch,
                self.advantage: advantage_batch
            }
        )
        return {'actor_loss': actor_loss, 'actor_max_prob': actor_max_prob}

    def get_action(self, input_state, epsilon):
        action_prob = self.sess.run(self.action_prob, feed_dict={
                                    self.input: [input_state]})[0]
        action_prob = (epsilon / self.n_ac) + (1.0 - epsilon) * action_prob
        return np.random.choice(np.arange(self.n_ac), p=action_prob)

    def _eval_loss(self):
        if self.n_ac > 1:
            batch_size = tf.shape(self.input)[0]
            gather_indices = tf.range(batch_size) * \
                self.n_ac + self.action_select
            action_prob = tf.gather(tf.reshape(
                self.action_prob, [-1]), gather_indices)
            # policy gradient should ascent
            ad_log_prob = -(tf.log(action_prob) * self.advantage)
            # ad_log_prob = self.advantage * \
            #     tf.nn.softmax_cross_entropy_with_logits(
            #         logits=self.action, labels=self.action_select)
            return tf.reduce_mean(ad_log_prob)
        else:
            raise NotImplementedError

    def _update_target_opr(self):
        params = tf.trainable_variables('actor_accurate')
        params = sorted(params, key=lambda v: v.name)
        target_params = tf.global_variables('actor_target')
        target_params = sorted(params, key=lambda v: v.name)

        update_opr = []
        for param, target_param in zip(params, target_params):
            update_opr.append(target_param.assign(param))

        return update_opr

    def update_target(self):
        self.sess.run(self.update_target_opr)
