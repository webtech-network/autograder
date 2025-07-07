const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');
const fs = require('fs');
const path = require('path');

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
                test(`Endpoint ${endpoint} não deve aceitar método ${method}`, async () => await testUnexpectedMethod(endpoint, method));
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

        safeTest('GET / não retorna text/html', async () => {
            const response = await axios.get(`${BASE_URL}/`);
            expectContentType(response, 'text/html');
        })

        safeTest('GET /sugestao não retorna text/html', async () => {
            const response = await axios.get(`${BASE_URL}/sugestao?nome=test&ingredientes=test`);
            expectContentType(response, 'text/html');
        });

        safeTest('GET /contato não retorna text/html', async () => {
            const response = await axios.get(`${BASE_URL}/contato`);
            expectContentType(response, 'text/html');
        });

        safeTest('GET /api/lanches não retorna application/json', async () => {
            const response = await axios.get(`${BASE_URL}/api/lanches`);
            expectContentType(response, 'application/json');
        });

        safeTest('arquivo css estático style.css não retorna text/css', async () => {
            const response = await axios.get(`${BASE_URL}/css/style.css`);
            expectContentType(response, 'text/css');
        });


        safeTest('resposta final de POST /contato não retorna text/html (adaptativo)', async () => {
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

        safeTest('formulário da página index.html não possui campos de input com name attributes corretos', async () => {
            const response = await axios.get(`${BASE_URL}/`);
            const $ = cheerio.load(response.data);
            expectFormFields($, ['nome', 'ingredientes']);
        });

        safeTest('formulário da página contato.html não possui campos de input com name attributes corretos', async () => {
            const response = await axios.get(`${BASE_URL}/contato`);
            const $ = cheerio.load(response.data);
            expectFormFields($, ['nome', 'email', 'assunto', 'mensagem']);
        });
    });

    describe("Static File Organization", () => {
        
        let projectRoot = '';
        let projectFolderExists = false;

        beforeAll(() => {
            projectRoot = path.join(process.env.GITHUB_WORKSPACE || '', "submission");

            if (fs.existsSync(projectRoot)) {
                projectFolderExists = true;
            }
            console.log(`Project root is: ${projectRoot}`);
            console.log(`Project folder exists: ${projectFolderExists}`);
        });

        test('projeto contém outras dependências além do express', () => {
            if(!projectFolderExists) return;

            let packageJsonPath = path.join(projectRoot, 'package.json');
            let fileExists = fs.existsSync(packageJsonPath);

            if(!fileExists){
                console.log(`package.json file does not exist - path used: ${packageJsonPath}`);
                return;
            }

            const fileContent = fs.readFileSync(packageJsonPath, 'utf8');
            const packageJson = JSON.parse(fileContent);
            const dependencies = packageJson.dependencies || {};
            const dependencyKeys = Object.keys(dependencies);

            expect(dependencyKeys.length).toBeGreaterThan(1);
        });

        test('.gitignore não contém pasta node_modules', () => {
            if(!projectFolderExists) return;
        
            let gitIgnorePath = path.join(projectRoot, '.ignore');
            let fileExists = fs.existsSync(gitIgnorePath);

            if(!fileExists) return;

            let isCorrectlyIgnored = false;

            if (fs.existsSync(gitignorePath)) {
                const gitignoreContent = fs.readFileSync(gitignorePath, 'utf8');

                if (gitignoreContent.includes('node_modules')) {
                    isCorrectlyIgnored = true;
                }
            }
            expect(isCorrectlyIgnored).toBe(false);
        });
    });
});