import type { FC } from 'react'
import { useContext } from 'use-context-selector'
import type { ModelItem, ModelProvider } from '../declarations'
import {
  ConfigurateMethodEnum,
  ModelStatusEnum,
} from '../declarations'
import {
  languageMaps,
  modelTypeFormat,
  sizeFormat,
} from '../utils'
import ModelBadge from '../model-badge'
import Tab from './tab'
import AddModelButton from './add-model-button'
import Indicator from '@/app/components/header/indicator'
import { Settings01 } from '@/app/components/base/icons/src/vender/line/general'
import { ChevronDownDouble } from '@/app/components/base/icons/src/vender/line/arrows'
import Button from '@/app/components/base/button'
import I18n from '@/context/i18n'

type ModelListProps = {
  provider: ModelProvider
  models: ModelItem[]
  onCollapse: () => void
}
const ModelList: FC<ModelListProps> = ({
  provider,
  models,
  onCollapse,
}) => {
  const { locale } = useContext(I18n)
  const language = languageMaps[locale]
  const configurateMethods = provider.configurate_methods.filter(method => method !== ConfigurateMethodEnum.fetchFromRemote)
  const canCustomConfig = configurateMethods.includes(ConfigurateMethodEnum.customizableModel)
  const canSystemConfig = configurateMethods.includes(ConfigurateMethodEnum.predefinedModel)

  return (
    <div className='px-2 pb-2 rounded-b-xl'>
      <div className='py-1 bg-white rounded-lg'>
        <div className='flex items-center pl-1 pr-[3px]'>
          <span className='group shrink-0 flex items-center mr-2'>
            <span className='group-hover:hidden pl-1 pr-1.5 h-6 leading-6 text-xs font-medium text-gray-500'>
              {models.length} Models
            </span>
            <span
              className={`
                hidden group-hover:inline-flex items-center pl-1 pr-1.5 h-6 bg-gray-50 
                text-xs font-medium text-gray-500 cursor-pointer rounded-lg
              `}
              onClick={() => onCollapse()}
            >
              <ChevronDownDouble className='mr-0.5 w-3 h-3 rotate-180' />
              Collapse
            </span>
          </span>
          {
            canCustomConfig && canSystemConfig && (
              <span className='grow flex items-center'>
                <Tab active='all' onSelect={() => {}} />
              </span>
            )
          }
          {
            canCustomConfig && (
              <AddModelButton onClick={() => {}} />
            )
          }
        </div>
        {
          models.map(model => (
            <div
              key={model.model}
              className={`
                group flex items-center pl-2 pr-2.5 h-8 rounded-lg
                ${canCustomConfig && 'hover:bg-gray-50'}
              `}
            >
              <div className='shrink-0 mr-2' style={{ background: provider.icon_small[language] }} />
              <span
                className='shrink-0 mr-1 text-sm text-gray-900 truncate'
                title={model.label[language]}
              >
                {model.label[language]}
              </span>
              <div className='grow flex items-center gap-1'>
                <ModelBadge text={modelTypeFormat(model.model_type)}/>
                {
                  model.model_properties.mode && (
                    <ModelBadge text={(model.model_properties.mode as string).toLocaleUpperCase()}/>
                  )
                }
                {
                  model.model_properties.context_size && (
                    <ModelBadge text={sizeFormat(model.model_properties.context_size as number)}/>
                  )
                }
              </div>
              <div className='shrink-0 flex items-center'>
                {
                  canCustomConfig && (
                    <Button className='hidden group-hover:flex py-0 h-7 text-xs font-medium text-gray-700'>
                      <Settings01 className='mr-[5px] w-3.5 h-3.5' />
                      Config
                    </Button>
                  )
                }
                <Indicator
                  className='ml-2.5'
                  color={model.status === ModelStatusEnum.active ? 'green' : 'gray'}
                />
              </div>
            </div>
          ))
        }
      </div>
    </div>
  )
}

export default ModelList
