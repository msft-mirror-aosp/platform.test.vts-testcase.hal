/*
 * Copyright (C) 2025 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package android.vintf;

import android.vintf.ServiceInfo;

/**
 * Interface for retrieving information about services.
 */
interface IServiceInfoFetcher {

    /**
     * Lists all available services.
     *
     * @return A vector of strings, where each string represents the name of a
     *   service.
     */
    @utf8InCpp List<String> listAllServices();

    /**
     * Retrieves information about a specific service.
     *
     * @param name The name of the service.
     * @return A ServiceInfo object containing the service's information or
     * null if the service is not found.
     */
    ServiceInfo getServiceInfo(@utf8InCpp String name);
}
