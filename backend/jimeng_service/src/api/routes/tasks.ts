import Request from '@/lib/request/Request.ts';
import APIException from '@/lib/exceptions/APIException.ts';
import EX from '@/api/consts/exceptions.ts';
import { getAsyncTask } from '@/lib/async-task-store.ts';
import { refreshAsyncTask } from '@/api/controllers/task-poller.ts';

export default {
  prefix: '/v1/tasks',

  get: {
    '/:id': async (request: Request) => {
      const taskId = request.params.id;
      if (!taskId) {
        throw new APIException(EX.API_REQUEST_PARAMS_INVALID, '缺少任务ID');
      }

      const refreshed = await refreshAsyncTask(taskId);
      const task = refreshed || await getAsyncTask(taskId);
      if (!task) {
        throw new APIException(EX.API_TASK_NOT_FOUND, `异步任务不存在: ${taskId}`);
      }

      return {
        id: task.id,
        object: 'task',
        kind: task.kind,
        status: task.status,
        created_at: task.createdAt,
        updated_at: task.updatedAt,
        history_record_id: task.historyId,
        remote_status: task.remoteStatus,
        fail_code: task.failCode,
        result: task.result || null,
        error: task.error || null,
      };
    },
  },
};
