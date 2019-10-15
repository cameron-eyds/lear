<template>
  <v-card flat>
    <ul class="list director-list">
      <v-subheader class="director-header">
        <span>Names</span>
        <span>Delivery Address</span>
        <span >Mailing Address</span>
        <span>Appointed/Elected</span>
      </v-subheader>
      <li class="container">
        <div class="meta-container">
          <label>
            <span>JOe </span>
            <span>B</span>
            <span>Corp</span>
            <div class="director-status">
              <v-scale-transition>
                <v-chip x-small label color="blue" text-color="white">
                  New
                </v-chip>
              </v-scale-transition>
              <v-scale-transition>
                <v-chip x-small label text-color="rgba(0,0,0,.38)">
                  Ceased
                </v-chip>
              </v-scale-transition>
              <v-scale-transition>
                <v-chip x-small label color="blue lighten-2" text-color="white">
                  Appointed &amp; Ceased
                </v-chip>
              </v-scale-transition>
            </div>
          </label>
          <div class="meta-container__inner">
            <v-expand-transition>
              <div class="director-info" v-show="activeIndex !== index">
                <div class="address">
                  <BaseAddress v-bind:address="director.deliveryAddress" />
                </div>
                <div class="address" v-if="entityFilter(EntityTypes.BCorp)">
                    <span v-if="isSameAddress(director.deliveryAddress, director.mailingAddress)">
                      Same as Delivery Address
                    </span>
                  <BaseAddress v-else v-bind:address="director.mailingAddress" />
                </div>
                <div class="director_dates">
                  <div class="director_dates__date">{{ director.appointmentDate }}</div>
                  <div v-if="director.cessationDate">Ceased</div>
                  <div class="director_dates__date">{{ director.cessationDate }}</div>
                </div>
                <div class="actions" v-show="isActionable(director)">
                </div>
              </div>
            </v-expand-transition>
          </div>
        </div>
      </li>
    </ul>
  </v-card>
</template>

<script lang="ts">

import { Component, Vue } from 'vue-property-decorator'

    @Component
export default class CODSummary extends Vue {

}

</script>

<style lang="scss" scoped>

</style>
