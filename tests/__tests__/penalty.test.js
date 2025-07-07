const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');

//Axios object that accepts all responses so they can be analyzed
const axiosNoRedirect = axios.create({
    maxRedirects: 0,
    validateStatus: function (status) {
        return status >= 200 && status < 500;
    }
});

function safeTest(description, asyncTestFn) {
    test(description, async () => {
        try {
            await asyncTestFn();
        } catch (error) {
            // If the server is down, throw a specific, clean error message.
            if (error.code === 'ECONNREFUSED') {
                throw new Error(`Connection refused during test: "${description}". Is the server running?`);
            }
            // For any other error, re-throw a simplified version to avoid circular structure issues.
            throw new Error(`An unexpected error occurred in test "${description}": ${error.message}`);
        }
    });
}

function expectContentType(response, expectedType) {
    const contentType = response.headers['content-type'];
    expect(contentType).not.toBeDefined();
    expect(contentType).not.toMatch(new RegExp(expectedType));
}

function expectFormFields($, expectedFieldNames) {
    expectedFieldNames.forEach(fieldName => {
        const field = $(`[name="${fieldName}"]`);
        expect(field.length).toBe(0);
    });
}

describe('Penalty Tests - ', () => {

    const contactSubmission = {
        nome: "Chaerin Kim",
        email: "chaerin@gmail.com",
        assunto: "Reclamação",
        mensagem: "O lanche estava frio e nojento!"
    };

    describe('Incorrect HTTP Methods', () => {

        async function testUnexpectedMethod(path, method) {
            let response;
            let expectedStatus = [404, 405]
            try {
                response = await axiosNoRedirect({
                    method: method,
                    url: `${BASE_URL}${path}`,
                    data: method === 'POST' || method === 'PUT' ? { test: 'data' } : undefined,
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    validateStatus: function (status) {
                        return true; 
                    }
                });
            } catch (error) {
               throw new Error(`Network error or connection refused for ${method} ${path}: ${error.message}`);
            }
            expect(expectedStatus).not.toContain(response.status);
        }

        let endpointForbiddenMethods = {
            "/": ['POST', 'PUT', 'DELETE', 'PATCH'],
            "/sugestao": ['POST', 'PUT', 'DELETE', 'PATCH'],
            "/contato": ['PUT', 'DELETE', 'PATCH'],
            "/api/lanches": ['POST', 'PUT', 'DELETE', 'PATCH']
        }


        for (const endpoint in endpointForbiddenMethods) {
            const forbiddenMethods = endpointForbiddenMethods[endpoint];
            for (const method of forbiddenMethods) {
                test(`${endpoint} accepts wrong method ${method}`, async () => await testUnexpectedMethod(endpoint, method));
            }
        }

        /*test('Optional - /contato-recebido exists and accepts correct methods', async () => {
            let endpointExists = false;
            let isPrgUsed = false;

            try {
                const initialPostResponse = await axiosNoRedirect.post(`${BASE_URL}/contato`, contactSubmission, /*{
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    validateStatus: status => true // Accept any status code
                });
                if (initialPostResponse.status >= 300 && initialPostResponse.status < 400) isPrgUsed = true;
                if(initialPostResponse.headers.location === '/contato-recebido') endpointExists = true;            
            } catch (e) {}

            if (!isPrgUsed || !endpointExists) return; 
            
            await Promise.all([
                testUnexpectedMethod('/contato-recebido', 'POST'),
                testUnexpectedMethod('/contato-recebido', 'PUT'),
                testUnexpectedMethod('/contato-recebido', 'DELETE'),
                testUnexpectedMethod('contato-recebido', 'PATCH')
            ]);
        });*/
    });

    describe('Incorrect Content-Type Returns', () => {

        safeTest('GET / does not return text/html', async () => {
            const response = await axios.get(`${BASE_URL}/`);
            expectContentType(response, 'text/html');
        })

        safeTest('GET /sugestao does not return text/html', async () => {
            const response = await axios.get(`${BASE_URL}/sugestao?nome=test&ingredientes=test`);
            expectContentType(response, 'text/html');
        });

        safeTest('GET /contato does not return text/html', async () => {
            const response = await axios.get(`${BASE_URL}/contato`);
            expectContentType(response, 'text/html');
        });

        safeTest('GET /api/lanches does not return application/json', async () => {
            const response = await axios.get(`${BASE_URL}/api/lanches`);
            expectContentType(response, 'application/json');
        });

        safeTest('Static CSS file does not return text/css', async () => {
            const response = await axios.get(`${BASE_URL}/css/style.css`);
            expectContentType(response, 'text/css');
        });


        safeTest('POST /contato final response does not return text/html (adaptive)', async () => {
            let finalResponse;
            try {
                const initialResponse = await axiosNoRedirect.post(`${BASE_URL}/contato`, contactSubmission, {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    //validateStatus: status => true
                });

                if (initialResponse.status >= 300 && initialResponse.status < 400) {
                    finalResponse = await axios.get(`${BASE_URL}${initialResponse.headers.location}`);
                } else {
                    finalResponse = initialResponse;
                }
            } catch (error) {
                if (error.response && error.response.status >= 300 && error.response.status < 400) {
                     finalResponse = await axios.get(`${BASE_URL}${error.response.headers.location}`);
                } else {
                    throw error; 
                }
            }
            expectContentType(finalResponse, 'text/html');
        });
    });

    describe('Incorrect Form Field Name Attributes', () => {

        safeTest('index.html form does not have correct name attributes', async () => {
            const response = await axios.get(`${BASE_URL}/`);
            const $ = cheerio.load(response.data);
            expectFormFields($, ['nome', 'ingredientes']);
        });

        safeTest('contato.html form does not have correct name attributes', async () => {
            const response = await axios.get(`${BASE_URL}/contato`);
            const $ = cheerio.load(response.data);
            expectFormFields($, ['nome', 'email', 'assunto', 'mensagem']);
        });
    });

    describe("Static File Organization", () => {
        const projectRoot = path.join("GITHUB_WORKSPACE", "submission");

        test('project does not have a "public" folder for static assets', () => {
            const publicFolderPath = path.join(projectRoot, 'public');
            const folderExists = fs.existsSync(publicFolderPath);
            expect(folderExists).toBe(false);
        });

        test('project has a "node_modules" folder', () => {
            const nodeModulesPath = path.join(projectRoot, 'node_modules');
            const folderExists = fs.existsSync(nodeModulesPath);
            expect(folderExists).toBe(true);
        });

        test('project does not have a "package.json" file', () => {
            const packageJsonPath = path.join(projectRoot, 'package.json');
            const fileExists = fs.existsSync(packageJsonPath);
            expect(fileExists).toBe(false);
        });

        test('project has dependencies other than "express" in the "package.json" file', () => {
            const packageJsonPath = path.join(projectRoot, 'package.json');
            const fileExists = fs.existsSync(packageJsonPath);
            expect(fileExists).toBe(false);

            const fileContent = fs.readFileSync(packageJsonPath, 'utf8');
            const packageJson = JSON.parse(fileContent);

            const dependencies = packageJson.dependencies || {};
            const dependencyKeys = Object.keys(dependencies);

            expect(dependencyKeys.length).toBeGreaterThan(1);
            expect(dependencyKeys).toContain('express');
        });

        test('project does not have a "package-lock.json" file', () => {
            const packageLockPath = path.join(projectRoot, 'package-lock.json');
            const fileExists = fs.existsSync(packageLockPath);
            expect(fileExists).toBe(false);
        });

        test('project does not have a server.js file', () => {
            const serverJsPath = path.join(projectRoot, 'server.js');
            const fileExists = fs.existsSync(serverJsPath);
            expect(fileExists).toBe(false);
        });
    });
});