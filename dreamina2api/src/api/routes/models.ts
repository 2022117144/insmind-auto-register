import _ from 'lodash';
import { parseRegionFromToken } from '@/api/controllers/core.ts';
import { getSupportedImageModels, getSupportedVideoModels } from '@/api/consts/common.ts';

export default {
    prefix: '/v1',

    get: {
        '/models': async (request) => {
            const authHeader = request.headers.authorization;
            const regionInfo = authHeader ? parseRegionFromToken(authHeader.replace(/^Bearer\s+/i, '').split(',')[0]) : null;
            const modelSet = regionInfo?.profile?.modelSet || 'cn';
            const imageModels = getSupportedImageModels(modelSet);
            const videoModels = getSupportedVideoModels(modelSet);

            return {
                "data": [
                    ...imageModels.map(id => ({
                        id,
                        object: 'model',
                        owned_by: 'insmind-api',
                        category: 'image'
                    })),
                    ...videoModels.map(id => ({
                        id,
                        object: 'model',
                        owned_by: 'insmind-api',
                        category: 'video'
                    }))
                ],
            };
        }
    }
};
