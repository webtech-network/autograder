const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');

let axiosNoRedirect = axios.create({ maxRedirects: 0 });

describe('Route - /', () => {
  let response;

  beforeAll(async () => {
    try {
      response = await axios.get(BASE_URL)
    } catch (error) {
      if (error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}. Is the Express server running?`);
      throw error;
    }
  });

  // 1) --- Basic connectivity checks ---
  describe('Status code and headers', () => {

    test('should return a 200 OK status code', () => {
      expect(response.status).toBe(200);
    });

    test('should return a Content-Type header of text/html', () => {
      expect(response.headers['content-type']).toMatch(/html/);
    });
  });


  // 2) --- HTML content checks ---
  describe('HTML Content Analysis', () => {
    let $;
    let $form;

    beforeAll(() => {
      $ = cheerio.load(response.data);
      $form = $('form')
    });

    test('should contain at least one form', () => {
      expect($form.length).toBeGreaterThan(0);
    });

    const expectedFormFields = [
      {
        name: 'nome',
        acceptableSelectors: ['input[type="text"]', 'textarea']
      },
      {
        name: 'ingredientes',
        acceptableSelectors: ['input[type="text"]', 'textarea']
      }
    ];

    test('should contain all expected form input fields with correct attributes', () => {
      expectedFormFields.forEach(field => {
        let foundField = false;

        for (const selector of field.acceptableSelectors) {
          const $input = $form.find(`${selector}[name="${field.name}"]`);
          if ($input.length > 0) foundField = true;
        }
        expect(foundField).toBe(true);
      });
    });
  });
}
);


/**
 * Tests for the suggestion route
 */
describe('Route - /sugestao', () => {
  const suggestion = {
    nome: "Banh mi",
    ingredientes: "cenoura, o nabo, a cebola, o açúcar e vinagre de arroz"
  };

  let response;
  let $;
  let queryString;

  beforeAll(async () => {
    queryString = new URLSearchParams(suggestion).toString();
    try {
      response = await axios.get(`${BASE_URL}/sugestao?${queryString}`);
      $ = cheerio.load(response.data);
    } catch (error) {
      if (error.code === 'ECONNREFUSED') {
        throw new Error(`Connection refused at ${BASE_URL}/sugestao?${queryString}. Is the Express server running?`);
      }
      response = error.response;
      if (!response) {
        throw error;
      }
      $ = cheerio.load(response.data);
    }
  });

  test('should accept GET request with query string', () => {
    expect(response.config.url).toContain(`?${queryString}`);
    expect(response.config.method).toBe('get');
  });

  test('should return 200 OK and Content-Type text/html', () => {
    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toMatch(/html/);
  });

  test('should not redirect (status code should be 200 directly)', () => {
    const isRedirect = response.status >= 300 && response.status < 400;
    expect(isRedirect).toBe(false);
  });


  describe('HTML Content Analysis', () => {
    test('should display the submitted "nome" in the HTML', () => {
      expect($.html()).toContain(suggestion.nome);
    });

    test('should display the submitted "ingredientes" in the HTML', () => {
      expect($.html()).toContain(suggestion.ingredientes);
    });

    test('should containt anchor to the root route', () => {
      const rootLink = $('a[href="/"]');
      expect(rootLink.length).toBeGreaterThanOrEqual(1);
    });
  });
});


describe('Route - /contato (GET)', () => {
  let response;
  let $;
  beforeAll(async () => {
    try {
      response = await axios.get(`${BASE_URL}/contato`);
      $ = cheerio.load(response.data);
    } catch (error) {
      if (error.code === 'ECONNREFUSED') {
        throw new Error(`Connection refused at ${BASE_URL}/contato. Is the Express server running?`);
      }
      response = error.response;
      if (!response) {
        throw error;
      }
      $ = cheerio.load(response.data);
    }
  });

  test('should return 200 OK and Content-Type text/html', () => {
    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toMatch(/html/);
  });

  test('should contain an input field for "nome"', () => {
    const nomeInput = $('[name="nome"]');
    expect(nomeInput.length).toBeGreaterThan(0);
    expect(nomeInput.is('input[type="text"]') || nomeInput.is('textarea')).toBe(true);
  });

  test('should contain an input field for "email"', () => {
    const emailInput = $('[name="email"]');
    expect(emailInput.length).toBeGreaterThan(0);
    expect(emailInput.is('input[type="email"]') || emailInput.is('input[type="text"]')).toBe(true);
  });

  test('should contain an input field for "assunto"', () => {
    const assuntoInput = $('[name="assunto"]');
    expect(assuntoInput.length).toBeGreaterThan(0);
    expect(assuntoInput.is('input[type="text"]') || assuntoInput.is('textarea')).toBe(true);
  });

  test('should contain a textarea or input for "mensagem"', () => {
    const mensagemInput = $('[name="mensagem"]');
    expect(mensagemInput.length).toBeGreaterThan(0);
    expect(mensagemInput.is('textarea') || mensagemInput.is('input[type="text"]')).toBe(true);
  });

  test('should contain a submit button', () => {
    const submitButton = $('button[type="submit"], input[type="submit"]');
    expect(submitButton.length).toBeGreaterThan(0);
  });

  test('should contain an anchor tag linking to the root route ("/")', () => {
    const rootLink = $('a[href="/"]');
    expect(rootLink.length).toBeGreaterThan(0);
  });
});

describe('Route - /contato (POST)', () => {
  const contactSubmission = {
    nome: "Sophie Nguyen",
    email: "tramanh@gmail.com",
    assunto: "Sugestão de Evento",
    mensagem: "Gostaria de sugerir que vocês organizassem um evento de degustação de novos lanches!"
  };

  let finalResponse;
  let initialStatus;
  let initialLocation;
  let $;

  beforeAll(async () => {
    try {
      const responseFromPost = await axiosNoRedirect.post(`${BASE_URL}/contato`, contactSubmission, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });

      initialStatus = responseFromPost.status;
      initialLocation = responseFromPost.headers.location;

      if (initialStatus >= 300 && initialStatus < 400) {
        expect(initialLocation).toBe('/contato-recebido');
        finalResponse = await axios.get(`${BASE_URL}${initialLocation}`);
      } else {
        finalResponse = responseFromPost;
      }
      $ = cheerio.load(finalResponse.data);

    } catch (error) {
      if (error.code === 'ECONNREFUSED') {
        throw new Error(`Connection refused at ${BASE_URL}/contato. Is the Express server running?`);
      }
      if (error.response && error.response.status >= 300 && error.response.status < 400) {
        initialStatus = error.response.status;
        initialLocation = error.response.headers.location;
        expect(initialLocation).toBe('/contato-recebido');
        try {
          finalResponse = await axios.get(`${BASE_URL}${initialLocation}`);
          $ = cheerio.load(finalResponse.data);
        } catch (redirectError) {
          throw new Error(`Failed to follow redirect to ${initialLocation}: ${redirectError.message}`);
        }
      } else {
        finalResponse = error.response;
        if (!finalResponse) {
          throw error;
        }
        if (finalResponse.headers['content-type'] && finalResponse.headers['content-type'].includes('html')) {
          $ = cheerio.load(finalResponse.data);
        } else {
          $ = cheerio.load('');
        }
      }
    }
  });

  test('final response should be 200 OK and Content-Type text/html', () => {
    expect(finalResponse.status).toBe(200);
    expect(finalResponse.headers['content-type']).toMatch(/html/);
  });

  test('should either respond directly with HTML or redirect to /contato-recebido', () => {
    if (initialStatus >= 300 && initialStatus < 400) {
      expect(initialStatus).toBeGreaterThanOrEqual(300);
      expect(initialStatus).toBeLessThan(400);
      expect(initialLocation).toBe('/contato-recebido');
      console.log('Detected PRG pattern: POST resulted in a 3xx redirect.');
    } else {
      expect(initialStatus).toBe(200);
      expect(initialLocation).toBeUndefined();
      console.log('Detected direct HTML response for POST.');
    }
  });

  describe('HTML Content Analysis (Final Page)', () => {
    test('should display the submitted "nome"', () => {
      expect($.html()).toContain(contactSubmission.nome);
    });

    test('should display the submitted "email"', () => {
      expect($.html()).toContain(contactSubmission.email);
    });

    test('should display the submitted "assunto"', () => {
      expect($.html()).toContain(contactSubmission.assunto);
    });

    test('should display the submitted "mensagem"', () => {
      expect($.html()).toContain(contactSubmission.mensagem);
    });

    test('should contain an anchor tag linking to the root route ("/")', () => {
      const rootLink = $('a[href="/"]');
      expect(rootLink.length).toBeGreaterThan(0);
    });
  });
});

describe('Route - /api/lanches', () => {
  let response;
  let lanches;

  beforeAll(async () => {
    try {
      response = await axios.get(`${BASE_URL}/api/lanches`);
      lanches = response.data;
    } catch (error) {
      if (error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}/api/lanches. Is the Express server running?`);
      throw error;
    }
  });

  // --- Basic Connectivity Checks ---
  describe('Basic Connectivity and Headers', () => {
    test('should return a 200 OK status code', () => {
      expect(response.status).toBe(200);
    });

    test('should return a Content-Type header of application/json', () => {
      expect(response.headers['content-type']).toMatch(/application\/json/);
    });
  });


  // --- JSON Data Structure and Type Validation ---
  describe('JSON Data Structure Validation', () => {
    test('should return an array of lanches', () => {
      expect(Array.isArray(lanches)).toBe(true);
    });

    test('should return an array with at least 3 lanches', () => {
      expect(lanches.length).toBeGreaterThan(2);
    });

    test('each lanche object in the array should have the required attributes: id, nome ingredientes', () => {
      lanches.forEach(lanche => {
        expect(lanche).toHaveProperty('id');
        expect(lanche).toHaveProperty('nome');
        expect(lanche).toHaveProperty('ingredientes');
      });
    });

    test('each lanche attribute should have the correct data type and not be blank, 0 or null', () => {
      lanches.forEach(lanche => {
        expect(typeof lanche.id).toBe('number');
        expect(Number.isInteger(lanche.id)).toBe(true);
        expect(lanche.id).toBeGreaterThan(0);

        expect(typeof lanche.nome).toBe('string');
        expect(lanche.nome.length).toBeGreaterThan(0);

        expect(typeof lanche.ingredientes).toBe('string');
        expect(lanche.ingredientes.length).toBeGreaterThan(0);
      });
    });
  });
}
);