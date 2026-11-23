// APIの型。`schema.d.ts`（OpenAPIから生成。手で編集しない）の名前に、わかりやすい別名を付ける。
// APIを変えたら、`npm run gen:api` で、型を作り直す。

import type { components } from './schema'

type Schemas = components['schemas']

export type Slot = Schemas['SlotOut']
export type ExperienceListItem = Schemas['ExperienceListItem']
export type ExperienceDetail = Schemas['ExperienceDetail']
export type BookingCreate = Schemas['BookingCreate']
export type BookingCreated = Schemas['BookingCreated']
export type BookingLookup = Schemas['BookingLookup']
export type BookingStatusOut = Schemas['BookingStatusOut']
export type ConciergeResponse = Schemas['ConciergeResponse']
export type Suggestion = Schemas['SuggestionOut']
export type Category = Schemas['Category']
